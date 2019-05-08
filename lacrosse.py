#!/usr/bin/env python2.7

from __future__ import print_function

from rfm69 import Rfm69
import rfm69
import sensors
from sensors import rawsensor
import sys
import time

if Rfm69.Test(1):
	rfm = Rfm69(1, 24) #when using the RaspyRFM twin
elif Rfm69.Test(0):
	rfm = Rfm69() #when using a single single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()
	
rfm.SetParams(
    Freq = 868.312, #MHz center frequency
    Datarate = 9.579, #17.241, #kbit/s baudrate
    ModulationType = rfm69.FSK, #modulation
    Deviation = 90, #90 kHz frequency deviation
    SyncPattern = [0x2d, 0xd4], #syncword
    Bandwidth = 200, #kHz bandwidth
    RssiThresh = -100 #-100 dB RSSI threshold
    )

data = []

print("Waiting for sensors...")
while 1:
    data = rfm.ReceivePacket(7)
    obj = rawsensor.CreateSensor(data)
    print(str(obj))
