#!/usr/bin/env python2.7

import RaspyRFM
import sensors
from sensors import rawsensor
import sys
import time
import threading

if RaspyRFM.RaspyRFM.Test(1):
	print("Found RaspyRFM twin")
	rfm = RaspyRFM.RaspyRFM(1, 24) #when using the RaspyRFM twin
elif RaspyRFM.RaspyRFM.Test(0):
	print("Found RaspyRFM single")
	rfm = RaspyRFM.RaspyRFM() #when using a single single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

rfm.SetParams(
    Freq = 868.30, #MHz center frequency
    Datarate = 9.579, #kbit/s baudrate
    ModulationType = RaspyRFM.FSK, #modulation
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
			print "Switch baudrate to " + str(dr) + " kbit/s"
			rfm.SetParams(Datarate = dr)
			self.baud = not self.baud

baudChanger = BaudChanger()
baudChanger.daemon = True
baudChanger.start()

print "Waiting for sensors..."
while 1:
	data = rfm.ReceivePacket(5)
	if data == None:
		continue

	obj = rawsensor.CreateSensor(data).GetData()
	if not 'ID' in obj:
		continue
	print(obj)
