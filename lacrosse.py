#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sensors
from sensors import rawsensor
import sys
import time

rfm = Rfm69()

rfm.SetParams(
    Freq = 868.300, #MHz center frequency
    Datarate = 9.579, #17.241, #kbit/s baudrate
    ModulationType = rfm69.FSK, #modulation
    Deviation = 30, #30 kHz frequency deviation
    SyncPattern = [0x2d, 0xd4], #syncword
    Bandwidth = 200, #kHz bandwidth
    LnaGain = 0x88,
    RssiThresh = 220
    )
    
print hex(rfm.ReadReg(0x07))
print hex(rfm.ReadReg(0x08))
print hex(rfm.ReadReg(0x09))

    
data = []

while 1:
    data = rfm.ReceivePacket(7)
    obj = rawsensor.CreateSensor(data)
    print(str(obj))
    
