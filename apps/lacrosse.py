#!/usr/bin/env python

from raspyrfm import *
import sensors
from sensors import rawsensor
import sys, time, threading, argparse

rfm = None

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=0)
args = parser.parse_args()

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
	baud = False
	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		while True:
			time.sleep(15)
			if self.baud:
				dr = 9.579
			else:
				dr = 17.241
			print("Switch baudrate to " + str(dr) + " kbit/s")
			rfm.receive_stop()
			rfm.set_params(Datarate = dr)
			self.baud = not self.baud

baudChanger = BaudChanger()
baudChanger.daemon = True
baudChanger.start()

while 1:
	data = rfm.receive(12)
	if data == None:
		continue

	obj = rawsensor.CreateSensor(data).GetData()
	if not 'ID' in obj:
		continue
	print(obj)
