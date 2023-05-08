from __future__ import print_function
from . import rfmbase
import spidev, sys, threading, time
import RPi.GPIO as GPIO

FXOSC = 32E6
FSTEP = FXOSC / (1<<19)

# RaspyRFM module pinout
# Connect 10-pin header to pins 17-26 on PI
# Connect 12-pin header to pins 15-26 in PI
# -----------------------------
# |      |     |single| twin  |
# |Raspi |Raspi|RFM69 |RFM69  |
# |Name  |Pin  |Pin   |Pin    |
# |---------------------------|
# |GPIO22| 15  |---   |DIO2#2 |
# |GPIO23| 16  |DIO2  |DIO2#1 |
# |3V3   | 17  |3.3V  |3.3V   |
# |GPIO24| 18  |DIO1* |DIO0#2 |
# |MOSI  | 19  |MOSI  |MOSI   |
# |GND   | 20  |GND   |GND    |
# |MISO  | 21  |MISO  |MISO   |
# |GPIO25| 22  |DIO0  |DIO0#1 |
# |SCKL  | 23  |SCK   |SCK    |
# |CE0   | 24  |NSS   |NSS#1  |
# |GND   | 25  |GND   |GND    |
# |CE1   | 26  |---   |NSS#2  |
# -----------------------------
# * PCB jumper!

# RFM69 registers
# common registers
RegFifo = 0x00
RegOpMode = 0x01
RegDataModul = 0x02
RegBitrateMsb = 0x03
RegBitrateLsb = 0x04
RegFdevMsb = 0x05
RegFdevLsb = 0x06
RegFrfMsb = 0x07
RegFrfMid = 0x08
RegFrfLsb = 0x09
RegOsc1 = 0x0A
RegAfcCtrl = 0x0B
RegListen1 = 0x0D
RegListen2 = 0x0E
RegListen3 = 0x0F
RegVersion = 0x10
# TX registers
RegPaLevel = 0x11
RegPaRamp = 0x12
RegOcp = 0x13
# RX registers
RegLna = 0x18
RegRxBw = 0x19
RegAfcBw = 0x1A
RegOokPeak = 0x1B
RegOokAvg = 0x1C
RegOokFix = 0x1D
RegAfcFei = 0x1E
RegAfcMsb = 0x1F
RegAfcLsb = 0x20
RegFeiMsb = 0x21
RegFeiLsb = 0x22
RegRssiConfig = 0x23
RegRssiValue = 0x24
# IRQ & pin mapping registers
RegDioMapping1 = 0x25
RegDioMapping2 = 0x26
RegIrqFlags1 = 0x27
RegIrqFlags2 = 0x28
RegRssiThresh = 0x29
RegRxTimeout1 = 0x2A
RegRxTimeout2 = 0x2B
# packet engine registers
RegPreambleMsb = 0x2C
RegPreambleLsb = 0x2D
RegSyncConfig = 0x2E
RegSyncValue1 = 0x2F
RegPacketConfig1 = 0x37
RegPayloadLength = 0x38
RegNodeAdrs = 0x39
RegBroadcastAdrs = 0x3A
RegAutoModes = 0x3B
RegFifoThresh = 0x3C
RegPacketConfig2 = 0x3D
RegAesKey1 = 0x3E
RegTemp1 = 0x4E
RegTemp2 = 0x4F
RegTestLna = 0x58
RegTestPa1 = 0x5A
RegTestPa2 = 0x5C
RegTestDagc = 0x6F
RegTestAfc = 0x71

InterPacketRxDelay = 4 # Bitposition
RestartRx = 2
AutoRxRestartOn = 1
AesOn = 0

# Modulation type
OOK = 1
FSK = 0

# DcFree
DcFree_None = 0
DcFree_Manchester = 1
DcFree_Whitening = 2

# RFM69 modes
MODE_SLEEP = 0
MODE_STDBY = 1
MODE_FS = 2
MODE_TX = 3
MODE_RX = 4

# DIO packet mode
DIO0_PM_CRC = 0
DIO0_PM_PAYLOAD = 1
DIO0_PM_SYNC = 2
DIO0_PM_RSSI = 3
DIO0_PM_SENT = 0
DIO0_PM_TXDONE = 1
DIO0_PM_PLLLOCK = 3

class Rfm69(rfmbase.RfmBase):
	def __init__(self, cs = 0, gpio_int = 25):
		if not rfmbase.RfmBase.test(cs, 0x24):
			print("ERROR! RFM69 not found", file=sys.stderr)
			return

		rfmbase.RfmBase.__init__(self, cs)

		self.__irqEvent = threading.Event()
		self.__rxEvent = threading.Event()
		self.__rxEvent.set()
		self.__gpio_int = gpio_int
		self.__mutex = threading.Lock()
		self.__syncsize = 4
		self.__fifothresh = 15

		self.__aes_on = False
		self.__isrfm69hw = False
		self.__rxMode = False

		print("RFM69 found on CS " + str(cs), file=sys.stderr)
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(gpio_int, GPIO.IN)
		GPIO.add_event_detect(gpio_int, GPIO.RISING, callback=self.__rfm_irq)

		self.__set_mode(MODE_STDBY)
		config = {}

		# SET DEFAULTS
		config[RegOpMode] = 0x04
		config[RegDataModul] = 0x00
		config[RegBitrateMsb] = 0x1A
		config[RegBitrateMsb + 1] = 0x0B
		config[RegFdevMsb] = 0x00
		config[RegFdevMsb + 1] = 0x52
		config[RegFrfMsb] = 0xE4
		config[RegFrfMsb + 1] = 0xC0
		config[RegFrfMsb + 2] = 0x00
		config[RegOsc1] = 0x41
		config[RegAfcCtrl] = 0x00
		config[0x0C] = 0x02 # reserved
		config[RegListen1] = 0x92
		config[RegListen2] = 0xF5
		config[RegListen3] = 0x20
		config[RegVersion] = 0x24
		config[RegPaLevel] = 0x9F
		config[RegPaRamp] = 0x09
		config[RegOcp] = 0x1A
		config[0x17] = 0x9B # reserved
		config[RegLna] = 0x88
		config[RegRxBw] = 0x55
		config[RegAfcBw] = 0x8B
		config[RegOokPeak] = 0x40
		config[RegOokAvg] = 0x80
		config[RegOokFix] = 0x06
		config[RegAfcFei] = 0x00
		config[RegAfcMsb] = 0x00
		config[RegAfcLsb] = 0x00
		config[RegFeiMsb] = 0x00
		config[RegFeiLsb] = 0x00
		config[RegRssiConfig] = 0x02
		config[RegDioMapping1] = 0x00
		config[RegDioMapping2] = 0x05
		config[RegIrqFlags1] = 0x80
		config[RegIrqFlags2] = 0x10
		config[RegRssiThresh] = 0xE4
		config[RegRxTimeout1] = 0x00
		config[RegRxTimeout2] = 0x00
		config[RegPreambleMsb] = 0x00
		config[RegPreambleLsb] = 0x00
		config[RegSyncConfig] = 0x98
		config[RegPacketConfig1] = 0x10
		config[RegPayloadLength] = 0x40
		config[RegNodeAdrs] = 0x00
		config[RegBroadcastAdrs] = 0x00
		config[RegAutoModes] = 0
		config[RegFifoThresh] = 0x8F
		config[RegPacketConfig2] = 0x02
		config[RegTemp1] = 0x01
		config[RegTemp2] = 0x00
		config[RegTestLna] = 0x1B
		config[RegTestDagc] = 0x30 # low beta 0
		config[RegTestAfc] = 0x00

		config[RegPacketConfig1] = 0x00 # Fixed length, CRC off, no adr

		for key in config:
			self._write_reg(key, config[key])

		self.__set_highPower()
		self.mode_standby()
		print("Init complete.", file = sys.stderr)

	def __rfm_irq(self, ch):
		self.__irqEvent.set()

	def __set_dio_mapping(self, dio, mapping):
		if dio > 3:
			reg = RegDioMapping2
			dio -= 3
		else:
			reg = RegDioMapping1
		dio *= 2
		self._set_reg(reg, 0xC0 >> dio, mapping << (6 - dio))

	def __set_highPower(self):
		# Must be called after initialization for rfm69hw
		if(self.__isrfm69hw == True):
			self._write_reg(RegOcp, 0x0F) # OCP OFF
			self._write_reg(RegPaLevel, (self.read_reg(RegPaLevel) & 0x1F) | 0x60) # PA0 OFF PA1 ON  PA2 ON
		else:
			self._write_reg(RegOcp, 0x1A) # OCP ON
			self._write_reg(RegPaLevel, (self.read_reg(RegPaLevel) & 0x1F) | 0x80) # PA0 ON  PA1 OFF PA2 OFF

	def __set_highPowerRegs(self, mode):
        	# Registers only present in rfm69hw
		if(self.__isrfm69hw):
			if(mode == MODE_TX):
				self._write_reg(RegTestPa1, 0x5D)
				self._write_reg(RegTestPa2, 0x7C)
			else:
				self._write_reg(RegTestPa1, 0x55)
				self._write_reg(RegTestPa2, 0x70)

	def __set_mode(self, mode):
		self._write_reg(RegOpMode, mode << 2)
		self.__set_highPowerRegs(mode)
		self.__mode = mode
		while ((self.read_reg(RegIrqFlags1) & (1<<7)) == 0):
			pass

	def read_rssi_value(self):
		return self.read_reg(RegRssiValue)

	def mode_standby(self):
		self.__set_mode(MODE_STDBY)

	def set_params(self, **params):
		self.__mutex.acquire()
		for key in params:
			value = params[key]
			if key == "Freq":
				fword = int(round(value * 1E6 / FSTEP))
				self._write_reg(RegFrfMsb, fword >> 16)
				self._write_reg(RegFrfMid, fword >> 8)
				self._write_reg(RegFrfLsb, fword)

			elif key == "TxPower":
				pwr = int(value + 18)
				if(self.__isrfm69hw == True):
					self._write_reg(RegPaLevel, 0x60 | (pwr & 0x1F))
				else:
					self._write_reg(RegPaLevel, 0x80 | (pwr & 0x1F))

			elif key == "IsRFM69HW":
				self.__isrfm69hw = value
				if(value == True):
					self._write_reg(RegPaLevel, (self.read_reg(RegPaLevel) & 0x1F) | 0x60)
				else:
					self._write_reg(RegPaLevel, (self.read_reg(RegPaLevel) & 0x1F) | 0x80)

			elif key == "Datarate":
				rate = int(round(FXOSC / (value * 1000)))
				self._write_reg_word(RegBitrateMsb, rate)

			elif key == "Deviation":
				dev = int(round(value * 1000 / FSTEP))
				self._write_reg_word(RegFdevMsb, dev)

			elif key == "ModulationType":
				self._set_reg(RegDataModul, 0x18, value << 3)

			elif key == "ModulationShaping":
				self._set_reg(RegDataModul, 0x03, value)

			elif key == "SyncPattern":
				conf = 0
				self.__syncsize = len(value)
				if (len(value)) > 0:
					conf = ((len(value) - 1) & 0x07) << 3
					conf |= 1<<7
				else:
					conf = 1<<6
				self._write_reg(RegSyncConfig,	 conf)
				for i, d in enumerate(value):
					self._write_reg(RegSyncValue1 + i, d)

			elif key == "AesKey":
				if (len(value)) > 0:
					self._set_reg(RegPacketConfig2, 1<<0, 1<<0) # AES on
					self.__aes_on = True
				else:
					self._set_reg(RegPacketConfig2, 1<<0, 0<<0) # AES off
					self.__aes_on = False
				for i, d in enumerate(value):
					self._write_reg(RegAesKey1 + i, d)

			elif key == "Bandwidth":
				RxBw = FXOSC / value / 1000 / 4
				e = 0
				while (RxBw > 32) and (e < 7):
					e += 1
					RxBw /= 2
				RxBw = RxBw / 4 - 4
				RxBw = max(RxBw, 0)
				m = int(RxBw)
				self._set_reg(RegRxBw, 0x1F, m<<3 | e)

			elif key == "AfcBandwidth":
				RxBw = FXOSC / value / 1000 / 4
				e = 0
				while (RxBw > 32) and (e < 7):
					e += 1
					RxBw /= 2
				RxBw = RxBw / 4 - 4
				RxBw = max(RxBw, 0)
				m = int(RxBw)
				self._set_reg(RegAfcBw, 0x1F, m<<3 | e)

			elif key == "Preamble":
				self._write_reg_word(RegPreambleMsb, value)

			elif key == "LnaGain":
				self._set_reg(RegLna, 0x07, value)

			elif key == "RssiThresh":
				th = -(value * 2)
				self._write_reg(RegRssiThresh, th)

			elif key == "Dagc":
				self._write_reg(RegDagc, value)

			elif key == "AfcFei":
				self._write_reg(RegAfcFei, value)

			elif key == "Callback":
				self.__callback = value

			elif key == "DcFree":
				self._set_reg(RegPacketConfig1, 3<<5, value<<5)

			elif key == "OokThreshType":
				self._set_reg(RegOokPeak, 3<<6, value<<6)

			elif key == "OokFixedThresh":
				self._write_reg(RegOokFix, value)

			elif key == "OokPeakThreshDec":
				self._set_reg(RegOokPeak, 7<<0, value)

			else:
				print("Unrecognized option >>" + key + "<<", file=sys.stderr)

		#self.mode_standby()
		self.__mutex.release()

	def __wait_int(self):
		if GPIO.input(self.__gpio_int):
			return True
		while not self.__irqEvent.wait(0.5):
			pass
		return GPIO.input(self.__gpio_int)

	def whiten_hope(self, data):
		lfsr = 0x3fe
		for i, d in enumerate(data):
			data[i] = data[i] ^ ((lfsr >> 2) & 0xFF)
			# roll LFSR
			for j in range(8):
				if ((lfsr >> 5) ^ lfsr) & 0x10 != 0:
					lfsr |= 1<<0
				lfsr <<= 1
			lfsr &= 0x3ff

	def whiten_ti(self, data):
		lfsr = 0x1ff
		for i, d in enumerate(data):
			data[i] = data[i] ^ (lfsr & 0xFF)
			for i in range(8):
				if ((lfsr >> 5) ^ lfsr) & 0x01 != 0:
					lfsr |= 1<<9
				lfsr >>= 1

	def send(self, data, var_pack_format = False):
		self.__mutex.acquire()
		self.__irqEvent.clear()
		self.mode_standby()
		self.__mutex.release()

		# flush FIFO
		status = self.read_reg(RegIrqFlags2)
		while (status & 0x40 == 0x40):
			self.read_reg(RegFifo)
			status = self.read_reg(RegIrqFlags2)
		if var_pack_format:
			data.insert(0, len(data))
			self._set_reg(RegPacketConfig1, 1<<7, 1<<7)
		else:
			self._set_reg(RegPacketConfig1, 1<<7, 0<<7)
			self._write_reg(RegPayloadLength, 0 if len(data) > 255 else len(data))
		self.__set_dio_mapping(0, DIO0_PM_SENT) # DIO0 -> PacketSent

		l = min(len(data), 64)
		if not self.__aes_on:
			self.__set_mode(MODE_TX)

		while True:
			self.write_fifo_burst(data[:l])
			data = data[l:]
			if len(data) == 0:
				break
			while True:
				status = self.read_reg(RegIrqFlags2)
				if (status & (1<<5)) == 0: # below fifothresh
					l = min(len(data), self.__fifothresh)
					break
				if (status & (1<<7)) == 0: # space for at least 1 bytearray
					l = 1
					break
		if self.__aes_on:
			self.__set_mode(MODE_TX)

		self.__wait_int()
		self.mode_standby()

	def read_fifo_wait(self, length):
		ret = []
		ready = False
		while length != 0 and self.__rxMode:
			flags = self.read_reg(RegIrqFlags2)
			if (flags & (1<<2)) != 0: # PayloadReady
				ready = True

			if (flags & (1<<5)) != 0: # FIFO level?
				l = self.__fifothresh if (length >= self.__fifothresh) or (length == -1) else length
				ret += self.read_fifo_burst(l)
				length -= l
				continue

			if (flags & (1<<6)) != 0 and ((length < self.__fifothresh) or ready):
				ret.append(self.read_reg(RegFifo))
				length -= 1
				continue

			if (flags == 0) and ready:
				break
		return ret

	def GetNoiseFloor(self):
		self.__mutex.acquire()
		# save values
		rssithresh = self.read_reg(RegRssiThresh)
		ookthresh = self.read_reg(RegOokFix)
		sync = self.read_reg(RegSyncConfig)

		self._write_reg(RegRssiThresh, 240)
		self._write_reg(RegSyncConfig, 1<<6) # no sync, always fill FIFO
		self._write_reg(RegPayloadLength, 0) # unlimited length
		self.__set_mode(MODE_RX)
		thresh = 40
		while True:
			self._write_reg(RegOokFix, thresh)
			for i in range(150):
				b = self.read_fifo_wait()
				if b != 0:
					thresh += 1
					break
			if i == 149:
				break

		# restore registers
		self._write_reg(RegRssiThresh, rssithresh)
		self._write_reg(RegOokFix, ookthresh)
		self._write_reg(RegSyncConfig, sync)
		self.mode_standby()
		self.__mutex.release()
		return thresh

	def receive_start(self, length):
		self.__mutex.acquire()
		self.__rxMode = True
		self.__rxEvent.clear()

		if length == -1:
			#variable length packet format
			self._set_reg(RegPacketConfig1, 1<<7, 1<<7)
			self._write_reg(RegPayloadLength, 255)
		else:
			#fixed or unlimited length packet format
			self._set_reg(RegPacketConfig1, 1<<7, 0<<7)
			self._write_reg(RegPayloadLength, length)

		if self.__syncsize > 0:
			self.__set_dio_mapping(0, DIO0_PM_SYNC) # DIO0 -> SyncAddress
		else:
			self.__set_dio_mapping(0, DIO0_PM_RSSI) # DIO0 -> RSSI
		self.__set_mode(MODE_RX)
		self.__irqEvent.clear()
		self.__mutex.release()

		if self.__wait_int():
			self._set_reg(RegAfcFei, 0x20, 0x20) # start FEI measurement

	def receive_stop(self):
		self.__mutex.acquire()
		self.__rxMode = False
		self.__irqEvent.set()
		self.__mutex.release()
		#wait until receiveroutine is ready
		self.__rxEvent.wait()

	def receive_end(self):
		self.__mutex.acquire()
		self.mode_standby()
		self.__rxMode = False
		self.__rxEvent.set()
		self.__mutex.release()

	def receive(self, length=-1):
		self.receive_start(length)
		rssi = -self.read_reg(RegRssiValue) / 2

		self.__mutex.acquire()
		if not self.__rxMode:
			self.mode_standby()
			self.__rxEvent.set()
			self.__mutex.release()
			return None
		self.__irqEvent.clear()
		self.__mutex.release()

		if self.__aes_on or (length > 0 and length <= 64):
			self.__set_dio_mapping(0, DIO0_PM_PAYLOAD) # DIO0 -> payload OK
			self.__wait_int()

		rxdata = self.read_fifo_wait(length)
		if length == -1:
			rxdata = rxdata[1:]
		self.__mutex.acquire()
		if not self.__rxMode:
			self.mode_standby()
			self.__rxEvent.set()
			self.__mutex.release()
			return None
		self.__mutex.release()


		afc = self.read_reg(RegAfcMsb) << 8
		afc = afc | self.read_reg(RegAfcLsb)
		if afc >= 0x8000:
			afc = afc - 0x10000

		fei = self.read_reg(RegFeiMsb) << 8
		fei = fei | self.read_reg(RegFeiLsb)
		if fei >= 0x8000:
			fei = fei - 0x10000

		self.receive_end()

		return (rxdata, rssi, afc, fei)
