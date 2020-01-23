import RPi.GPIO as GPIO
import spidev
import threading
import time

FXOSC = 32E6
FSTEP = FXOSC / (1<<19)

#------ Raspberry RFM Module connection -----
# RaspyRFM single module
# Connect to pins 17-26 on raspberry pi
#-------------------------------------------------#
# Raspi | Raspi | Raspi | RFM69 | RFM12 | PCB con #
# Name	| GPIO	| Pin	| Name	|  Name |  Pin	  #
#-------------------------------------------------#
# 3V3	|	-	|  17	| 3.3V	| VDD	|	1	  #
#  -	|  24	|  18	| DIO1	| FFIT	|	2	  # only when PCB jumper closed
# MOSI	|  10	|  19	| MOSI	| SDI	|	3	  #
# GND	|	-	|  20	| GND	| GND	|	4	  #
# MISO	|	9	|  21	| MISO	| SDO	|	5	  #
#  -	|  25	|  22	| DIO0	| nIRQ	|	6	  #
# SCKL	|  11	|  23	| SCK	| SCK	|	7	  #
# CE0	|	8	|  24	| NSS	| nSEL	|	8	  #
# CE1	|	7	|  26	| DIO2	| nFFS	|  10	  # only when PCB jumper closed
#-------------------------------------------------#

# RaspyRFM twin module with 10-pin connector
# Connect to pins 17-26 on raspberry pi
#-------------------------------------------------#
# Raspi | Raspi | Raspi | RFM69 | RFM12 | PCB con #
# Name	| GPIO	| Pin	| Name	|  Name |  Pin	  #
#-------------------------------------------------#
# 3V3	|	-	|  17	| 3.3V	| VDD	|	1	  #
#  -	|  24	|  18	| DIO0_2| FFIT	|	2	  #
# MOSI	|  10	|  19	| MOSI	| SDI	|	3	  #
# GND	|	-	|  20	| GND	| GND	|	4	  #
# MISO	|	9	|  21	| MISO	| SDO	|	5	  #
#  -	|  25	|  22	| DIO0_1| nIRQ	|	6	  #
# SCKL	|  11	|  23	| SCK	| SCK	|	7	  #
# CE0	|	8	|  24	| NSS1	| nSEL	|	8	  #
# CE1	|	7	|  26	| NSS2	| nFFS	|  10	  #
#-------------------------------------------------#

# RaspyRFM twin module with 12-pin connector
# Connect to pins 15-26 on raspberry pi
#-------------------------------------------------#
# Raspi | Raspi | Raspi | RFM69 | RFM12 | PCB con #
# Name	| GPIO	| Pin	| Name	|  Name |  Pin	  #
#-------------------------------------------------#
#  -	|  22	|  15	| DIO2_2|		|	1	  #
#  -	|  23	|  16	| DIO2_1|		|	2	  #
# 3V3	|	-	|  17	| 3.3V	| VDD	|	3	  #
#  -	|  24	|  18	| DIO0_2| FFIT	|	4	  #
# MOSI	|  10	|  19	| MOSI	| SDI	|	5	  #
# GND	|	-	|  20	| GND	| GND	|	6	  #
# MISO	|	9	|  21	| MISO	| SDO	|	7	  #
#  -	|  25	|  22	| DIO0_1| nIRQ	|	8	  #
# SCKL	|  11	|  23	| SCK	| SCK	|	9	  #
# CE0	|	8	|  24	| NSS1	| nSEL	|	10	  #
# CE1	|	7	|  26	| NSS2	| nFFS	|	12	  #
#-------------------------------------------------#

#RFM69 registers
#common registers
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
#TX registers
RegPaLevel = 0x11
RegPaRamp = 0x12
RegOcp = 0x13
#RX registers
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
#IRQ & pin mapping registers
RegDioMapping1 = 0x25
RegDioMapping2 = 0x26
RegIrqFlags1 = 0x27
RegIrqFlags2 = 0x28
RegRssiThresh = 0x29
RegRxTimeout1 = 0x2A
RegRxTimeout2 = 0x2B
#packet engine registers
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
RegTemp1 = 0x4E
RegTemp2 = 0x4F
RegTestLna = 0x58
RegTestDagc = 0x6F
RegTestAfc = 0x71

InterPacketRxDelay = 4 #Bitposition
RestartRx = 2
AutoRxRestartOn = 1
AesOn = 0

#Modulation type
OOK = 1
FSK = 0

#DcFree
DcFree_None = 0
DcFree_Manchester = 1
DcFree_Whitening = 2

#RFM69 modes
MODE_SLEEP = 0
MODE_STDBY = 1
MODE_FS = 2
MODE_TX = 3
MODE_RX = 4

#DIO packet mode
DIO0_PM_CRC = 0
DIO0_PM_PAYLOAD = 1
DIO0_PM_SYNC = 2
DIO0_PM_RSSI = 3
DIO0_PM_SENT = 0
DIO0_PM_TXDONE = 1
DIO0_PM_PLLLOCK = 3

class Rfm69(threading.Thread):
	@staticmethod
	def test(cs, gpio_dio0):
		spi = spidev.SpiDev()
		spi.open(0, cs)
		spi.max_speed_hz = 5000
		#Testing presence of module
		err = False
		for i in range(8):
			spi.xfer2([(RegSyncValue1 + i) | 0x80, 0x55])
			test = spi.xfer2([(RegSyncValue1 + i), 0x00])[1]
			if test != 0x55:
				err = True
				break
			temp = spi.xfer2([(RegSyncValue1 + i) | 0x80, 0xAA])
			test = spi.xfer2([(RegSyncValue1 + i), 0x00])[1]
			if test != 0xAA:
				err = True
				break
		spi.close()
		return not err

	def __init__(self, cs = 0, gpio_int = 25):
		if not self.test(cs, gpio_int):
			print("ERROR! RFM69 not found")
			return

		self.__event = threading.Event()
		self.__spi = spidev.SpiDev()
		self.__spi.open(0, cs)
		self.__spi.max_speed_hz=int(5E6)
		self.__gpio_int = gpio_int
		self.__mutex = threading.Lock()
		self.__syncsize = 4
		self.__fifothresh = 32

		print("RFM69 found on CS " + str(cs))
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(gpio_int, GPIO.IN)
		GPIO.add_event_detect(gpio_int, GPIO.RISING, callback=self.__rfm_irq)

		self.__set_mode(MODE_STDBY)
		config = {}

		#SET DEFAULTS
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
		config[RegTestDagc] = 0x30 #low beta 0
		config[RegTestAfc] = 0x00

		config[RegPacketConfig1] = 0x00 #Fixed length, CRC off, no adr

		for key in config:
			self.__write_reg(key, config[key])

		self.mode_standby()
		threading.Thread.__init__(self)
		print("Init complete.")

	def run(self):
		while True:
			time.sleep(0.5)

	def __rfm_irq(self, ch):
		self.__event.set()

	def __write_reg(self, reg, val):
		temp = self.__spi.xfer2([(reg & 0x7F) | 0x80, val & 0xFF])

	def __write_reg_word(self, reg, val):
		self.__write_reg(reg, (val >> 8) & 0xFF)
		self.__write_reg(reg + 1, val & 0xFF)

	def __set_reg(self, reg, mask, val):
		temp = self.read_reg(reg) & (~mask)
		temp |= val & mask
		self.__write_reg(reg, temp)

	def __set_dio_mapping(self, dio, mapping):
		if ((dio >= 0) and (dio <=3)):
			self.__set_reg(RegDioMapping1, 0xC0 >> (dio * 2), mapping << (6 - dio * 2))
		elif (dio == 5):
			self.__set_reg(RegDioMapping2, 0x03 << 4, mapping << 4)

	def __set_mode(self, mode):
		self.__write_reg(RegOpMode, mode << 2)
		self.__mode = mode
		while ((self.read_reg(RegIrqFlags1) & (1<<7)) == 0):
			pass

	def read_reg(self, reg):
		temp = self.__spi.xfer2([reg & 0x7F, 0x00])
		return temp[1]

	def read_fifo_burst(self, len):
		temp = self.__spi.xfer2([0x00] + [0x00] * len)
		return temp[1:]

	def write_fifo_burst(self, data):
		self.__spi.xfer2([0x80] + list(data))

	def read_reg_word(self, reg):
		temp = self.__spi.xfer2([reg & 0x7F, 0x00, 0x00])
		return (temp[1] << 8) | (temp[2])

	def read_rssi_value(self):
		return self.read_reg(RegRssiValue)

	def mode_standby(self):
		self.__set_mode(MODE_STDBY)

	def set_params(self, **params):
		self.__mutex.acquire()
		self.__event.set()
		for key in params:
			value = params[key]
			if key == "Freq":
				fword = int(round(value * 1E6 / FSTEP))
				self.__write_reg(RegFrfMsb, fword >> 16)
				self.__write_reg(RegFrfMid, fword >> 8)
				self.__write_reg(RegFrfLsb, fword)

			elif key == "TxPower":
				pwr = int(value + 18)
				self.__write_reg(RegPaLevel, 0x80 | (pwr & 0x1F))

			elif key == "Datarate":
				rate = int(round(FXOSC / (value * 1000)))
				self.__write_reg_word(RegBitrateMsb, rate)

			elif key == "Deviation":
				dev = int(round(value * 1000 / FSTEP))
				self.__write_reg_word(RegFdevMsb, dev)

			elif key == "ModulationType":
				self.__set_reg(RegDataModul, 0x18, value << 3)

			elif key == "ModulationShaping":
				self.__set_reg(RegDataModul, 0x03, value)

			elif key == "SyncPattern":
				conf = 0
				self.__syncsize = len(value)
				if (len(value)) > 0:
					conf = ((len(value) - 1) & 0x07) << 3
					conf |= 1<<7
				else:
					conf = 1<<6
				self.__write_reg(RegSyncConfig,	 conf)
				for i, d in enumerate(value):
					self.__write_reg(RegSyncValue1 + i, d)

			elif key == "Bandwidth":
				RxBw = FXOSC / value / 1000 / 4
				e = 0
				while (RxBw > 32) and (e < 7):
					e += 1
					RxBw /= 2
				RxBw = RxBw / 4 - 4
				RxBw = max(RxBw, 0)
				m = int(RxBw)
				self.__set_reg(RegRxBw, 0x1F, m<<3 | e)

			elif key == "AfcBandwidth":
				RxBw = FXOSC / value / 1000 / 4
				e = 0
				while (RxBw > 32) and (e < 7):
					e += 1
					RxBw /= 2
				RxBw = RxBw / 4 - 4
				RxBw = max(RxBw, 0)
				m = int(RxBw)
				self.__set_reg(RegAfcBw, 0x1F, m<<3 | e)

			elif key == "Preamble":
				self.__write_reg_word(RegPreambleMsb, value)

			elif key == "LnaGain":
				self.__set_reg(RegLna, 0x07, value)

			elif key == "RssiThresh":
				th = -(value * 2)
				self.__write_reg(RegRssiThresh, th)

			elif key == "Dagc":
				self.__write_reg(RegDagc, value)

			elif key == "AfcFei":
				self.__write_reg(RegAfcFei, value)

			elif key == "Callback":
				self.__callback = value

			elif key == "DcFree":
				self.__set_reg(RegPacketConfig1, 3<<5, value<<5)

			elif key == "OokThreshType":
				self.__set_reg(RegOokPeak, 3<<6, value<<6)

			elif key == "OokFixedThresh":
				self.___write_reg(RegOokFix, value)

			elif key == "OokPeakThreshDec":
				self.__set_reg(RegOokPeak, 7<<0, value)

			else:
				print("Unrecognized option >>" + key + "<<")

		self.mode_standby();
		self.__mutex.release()

	def __wait_int(self):
		self.__event.clear()
		if GPIO.input(self.__gpio_int):
			return
		while not self.__event.wait(0.5):
			if GPIO.input(self.__gpio_int):
				break

	def whiten_hope(self, data):
		lfsr = 0x3fe
		for i, d in enumerate(data):
			data[i] = data[i] ^ ((lfsr >> 2) & 0xFF)
			#roll LFSR
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

	def send_packet(self, data):
		self.__mutex.acquire()
		self.__event.set()
		self.mode_standby()

		#flush FIFO
		status = self.read_reg(RegIrqFlags2)
		while (status & 0x40 == 0x40):
			self.read_reg(RegFifo)
			status = self.read_reg(RegIrqFlags2)

		self.__write_reg(RegPayloadLength, 0) #unlimited length
		self.__write_reg(RegFifoThresh, 0x80 | self.__fifothresh) #start TX with 1st byte in FIFO
		self.__set_dio_mapping(0, DIO0_PM_SENT) #DIO0 -> PacketSent
		self.__set_mode(MODE_TX)

		l = min(len(data), 64)
		while True:
			self.write_fifo_burst(data[:l])
			data = data[l:]
			if len(data) == 0:
				break
			while True:
				status = self.read_reg(RegIrqFlags2)
				if (status & (1<<5)) == 0: #below fifothresh
					l = min(len(data), self.__fifothresh)
					break
				if (status & (1<<7)) == 0: #space for at least 1 bytearray
					l = 1
					break

		self.__wait_int()
		self.mode_standby()
		self.__mutex.release()

	def read_fifo_wait(self, length):
		ret = []
		while length > 0:
			flags = self.read_reg(RegIrqFlags2)
			if ((flags & (1<<5)) != 0) and (length >= 32): #FIFO level?
				ret += self.read_fifo_burst(self.__fifothresh)
				length -= self.__fifothresh
			if (flags & (1<<6)) != 0: #FIFO not empty?
				ret.append(self.read_reg(RegFifo))
				length -= 1
		return ret

	def GetNoiseFloor(self):
		self.__mutex.acquire()
		#save values
		rssithresh = self.read_reg(RegRssiThresh)
		ookthresh = self.read_reg(RegOokFix)
		sync = self.read_reg(RegSyncConfig)

		self.__write_reg(RegRssiThresh, 240)
		self.__write_reg(RegSyncConfig, 1<<6) #no sync, always fill FIFO
		self.__write_reg(RegPayloadLength, 0) #unlimited length
		self.__set_mode(MODE_RX)
		thresh = 40
		while True:
			self.__write_reg(RegOokFix, thresh)
			for i in range(150):
				b = self.read_fifo_wait()
				if b != 0:
					thresh += 1
					break;
			if i == 149:
				break;

		#restore registers
		self.__write_reg(RegRssiThresh, rssithresh)
		self.__write_reg(RegOokFix, ookthresh)
		self.__write_reg(RegSyncConfig, sync)
		self.mode_standby()
		self.__mutex.release()
		return thresh

	def __start_rx(self):
		self.__mutex.acquire()
		while True:
			self.__write_reg(RegPayloadLength, 0) #unlimited length
			self.__write_reg(RegFifoThresh, self.__fifothresh)
			if self.__syncsize > 0:
				self.__set_dio_mapping(0, DIO0_PM_SYNC) #DIO0 -> SyncAddress
			else:
				self.__set_dio_mapping(0, DIO0_PM_RSSI) #DIO0 -> RSSI
			self.__set_mode(MODE_RX)
			self.__mutex.release()
			self.__wait_int()
			self.__mutex.acquire()
			if self.__mode == MODE_RX:
				break;

	def start_rx(self, cb):
		self.__start_rx()
		cb()
		self.mode_standby()
		self.__mutex.release()

	def receive_packet(self, length):
		self.__start_rx()
		result = self.read_fifo_wait(length)

		rssi = -self.read_reg(RegRssiValue) / 2
		afc = self.read_reg(RegAfcMsb) << 8
		afc = afc | self.read_reg(RegAfcLsb)

		if afc >= 0x8000:
			afc = afc - 0x10000

		self.mode_standby()
		self.__mutex.release()
		return (result, rssi, afc)
