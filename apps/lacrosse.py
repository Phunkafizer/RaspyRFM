#!/usr/bin/env python

from raspyrfm import *
import sensors
from sensors import rawsensor
import sys, time, threading, argparse

rfm = None

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=0)
args = parser.parse_args()
mutex = threading.Lock()

if args.module > 0:
	rfm = RaspyRFM(args.module, RFM69)
else:
	rfm = RaspyRFM(2, RFM69) # first try module #2
	if rfm == None:
		rfm = RaspyRFM(1, RFM69) # then try module #1

if rfm == None:
	print("No RFM69 module found!")
	exit()

rfm.set_params(
	Freq = 868.30, #MHz center frequency
	Datarate = 9.579, #kbit/s baudrate
	ModulationType = rfm69.FSK, #modulation
	SyncPattern = [0x2d, 0xd4], #syncword
	Bandwidth = 150, #kHz bandwidth
	RssiThresh = -105, #dBm RSSI threshold
)

class BaudChanger(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.daemon = True
		#self.start()

	def run(self):
		baudrates = [9.579, 17.241]
		i = 0
		while True:
			time.sleep(15)
			rfm.receive_stop()

			i += 1
			if i == len(baudrates):
				i = 0
			bd = baudrates[i]

			print("Switch baudrate to " + str(bd) + " kbit/s")
			mutex.acquire()
			rfm.set_params(Datarate = bd)
			mutex.release()

baudChanger = BaudChanger()

while 1:
	mutex.acquire()
	data = rfm.receive(-1)
	mutex.release()

	if data == None:
		print("---")
		continue

	obj = rawsensor.CreateSensor(data).GetData()
	if not 'ID' in obj:
		continue
	print(obj)
