#!/usr/bin/env python3

from raspyrfm import *
import sys
import time
import threading

devices = {
	'0x19cf40': 'WallSchlaf',
	'0x1a2a84': 'HeatSchlaf1',
	'0x12c400': 'HeatSchlaf2',
	'0x192b8d': 'WallWohn',
	'0x192765': 'WallMusik',
	'0x1ac690': 'HeatWohnR',
	'0x1ac36b': 'HeatWohnL',
}

if raspyrfm_test(2, RFM69):
	print("Found RaspyRFM twin")
	rfm = RaspyRFM(2, RFM69) #when using the RaspyRFM twin
elif raspyrfm_test(1, RFM69):
	print("Found RaspyRFM single")
	rfm = RaspyRFM(1, RFM69) #when using a single single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

rfm.set_params(
	Freq = 868.300, #MHz center frequency
	ModulationType = rfm69.FSK, #modulation
	Datarate = 9.992, #kbit/s baudrate
	Deviation = 19.042, #kHz frequency deviation
	SyncPattern = [0xc6, 0x26, 0xc6, 0x26], #syncword
	Bandwidth = 150, #kHz bandwidth
	RssiThresh = -105, #dBm RSSI threshold
)

rxFifo = []
fifoEvent = threading.Event()
fifoMutex = threading.Lock()

class RxThread(threading.Thread):
	def __init__(self, rfm):
		self.__rfm = rfm
		threading.Thread.__init__(self)

	def __callback(self, rfm):
		frame = rfm.read_fifo_wait(1)
		len = frame[0] ^ 0xFF # invert due to whitening
		frame += rfm.read_fifo_wait(len)

		Mutex.acquire()
		rxFifo.append(frame)
		rxMutex.release()
		rxEvent.set()

	def run(self):
		while True:
			self.__rfm.receive_start(0)
			frame = self.__rfm.read_fifo_wait(1)
			framelen = frame[0] ^ 0xFF # invert due to whitening
			frame += self.__rfm.read_fifo_wait(framelen)
			self.__rfm.receive_end()
			fifoMutex.acquire()
			rxFifo.append(frame)
			fifoMutex.release()
			fifoEvent.set()

rxThread = RxThread(rfm)
rxThread.daemon = True
rxThread.start()

def Decode(frame):
	print(frame)
	# decode MAX! frame
	cnt = frame[1]
	flag = hex(frame[2])
	type = frame[3]
	srcadr = hex(frame[4] << 16 | frame[5] << 8 | frame[6])
	dstadr = hex(frame[7] << 16 | frame[8] << 8 | frame[9])
	grp = frame[10]
	payload = frame[11:]

	if srcadr in devices:
		srcadr = devices[srcadr]

	if dstadr in devices:
		dstadr = devices[dstadr]

	info = ""
	if type == 0x42:
		info = "set T: " + str(payload[0] / 2.0) + ' / act T:' + str(payload[1] / 10.0)

	if type == 0x40:
		info = "set T: " + str(payload[0] / 2.0)

	elif type == 0x60:
		devflags = payload[0]
		valve = payload[1]
		dst = payload[2] / 2.0
		info += ", mode " + str(devflags & 0x03)
		if (devflags & (1<<7)) != 0:
			info += ", bat err"
		if (devflags & (1<<6)) != 0:
			info += ", com err"
		if (devflags & (1<<5)) != 0:
			info += ", locked"
		info += ", valve " + str(valve) + "%"
		info += ", set T " + str(dst)

	elif type == 0x00:
		info = "FW " + str(payload[0] / 16) + "." + str(payload[0] % 16) + ", devtype " + str(payload[1]) + ", serial "
		for c in payload[3:]:
			info += chr(c)

	info += ", raw: " + str(payload)
	print(srcadr + "->" + dstadr + " type " + hex(type) + ': ' + info)

while True:
	if fifoEvent.wait(0.5) == False:
		continue

	left = True
	while left:
		fifoMutex.acquire()
		fifoEvent.clear()
		frame = rxFifo.pop(0)
		left = len(rxFifo) > 0
		fifoMutex.release()

		rfm.whiten_ti(frame)
		Decode(frame)
		if not left:
			break
