#!/usr/bin/env python

from raspyrfm import *
import sensors
from sensors import rawsensor
import sys
import time
import threading

if raspyrfm_test(2, RFM69):
	print("Found RaspyRFM twin")
	rfm = RaspyRFM(2, RFM69) #when using the RaspyRFM twin
elif raspyrfm_test(1, RFM69):
	print("Found RaspyRFM single")
	rfm = RaspyRFM(1, RFM69) #when using a single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

rfm.set_params(
	Freq = 868.30, #MHz center frequency
	Datarate = 9.579, #kbit/s baudrate
	ModulationType = rfm69.FSK, #modulation
	Deviation = 30, #kHz frequency deviation
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
