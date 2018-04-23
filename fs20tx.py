#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sensors
import sys
import time

if Rfm69.Test(1):
    rfm = Rfm69(1, 24) #when using the RaspyRFM twin
elif Rfm69.Test(0):
    rfm = Rfm69() #when using a single single 868 MHz RaspyRFM
else:
    print "No RFM69 module found!"
    exit()

rfm.SetParams(
    Freq = 868.350,
    Datarate = 5.0,
    TXPower = -10,
    ModulationType = rfm69.OOK,
    SyncPattern = [0x33, 0x33, 0x33, 0x33, 0x33, 0x33, 0x38],
    Preamble = 0
    )

data = []
bitcnt = 0

def AddBit(bit):
    global data
    global bitcnt
    if bit:
        if ((len(data) * 8) - bitcnt) < 6:
            data.append(0)
        
        data[bitcnt / 8] |= 0xE0 >> (bitcnt % 8)
        
        if (bitcnt % 8) > 2:
            data[(bitcnt / 8) + 1] |= (0xE0 << (8 - (bitcnt % 8))) & 0xFF
            
        bitcnt += 6
        
    else:
        if ((len(data) * 8) - bitcnt) < 4:
            data.append(0)
            
        data[bitcnt / 8] |= 0xC0 >> (bitcnt % 8)
        if (bitcnt % 8) > 4:
            data[(bitcnt / 8) + 1] |= (0xC0 << (8 - (bitcnt % 8))) & 0xFF
        
        bitcnt += 4
        
def AddByte(b):
    mask = 0x80
    while (mask):
        AddBit(b & mask)
        mask >>= 1
    cnt = 0
    while b:
        cnt += 1
        b &= b - 1
    AddBit(cnt & 1)
    
def MakeFS20Frame(hc, adr, cmd):
    q = 0
    AddByte(hc >> 8)
    AddByte(hc & 0xFF)
    q += hc >> 8
    q += hc & 0xFF
    AddByte(adr)
    q += adr
    if (cmd > 0xFF):
        AddByte(cmd >> 8)
        q += cmd >> 8
    AddByte(cmd & 0xFF)
    q += cmd & 0xFF
    q += 6
    AddByte(q & 0xFF)
    AddBit(0)

data = []
bitcnt = 0
MakeFS20Frame(int(sys.argv[1], 0), int(sys.argv[2], 0), int(sys.argv[3], 0))
for x in range(3):
    rfm.SendPacket(data)
