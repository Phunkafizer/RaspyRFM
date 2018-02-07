#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sensors
from sensors import rawsensor
import sys
import time

rfm = Rfm69()

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

print "Waiting for sensors..."
while 1:
    data = rfm.ReceivePacket(7)
    obj = rawsensor.CreateSensor(data)
    print(str(obj))
