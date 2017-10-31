#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sys
import time
#import types
#import os

rfm = Rfm69()
rfm.SetParams(
    Freq = 433.944,
    Datarate = 4.0, #1 / 250E-06 / 1000,
    Bandwidth = 24000,
    SyncPattern = [0x00, 0x08, 0x00],
    RssiThresh = -80,
    ModulationType = rfm69.OOK
    )
    
def staff(byte):
    res = 0
    res |= (byte & 1<<7) >> 4
    res |= (byte & 1<<5) >> 3
    res |= (byte & 1<<3) >> 2
    res |= (byte & 1<<1) >> 1
    return res

def decode(bindata):
  netdata = [0x00, 0x00, 0x00, 0x00]
  for i in range(0, 64, 2):
    if (bindata[i / 8] >> (i % 8)) & 0x01 == (bindata[i / 8] >> (i % 8 + 1)) &  0x01:
      print "Error", i, hex(bindata[i / 8]), hex(bindata[i / 8] >> (i % 8))
  for i in range(4):
    netdata[i] = staff(bindata[i * 2]) << 4 | staff(bindata[i * 2 + 1])
  
  print "decode: ",
  for i in range(4):
    print "{0:{fill}2x}".format(netdata[i], fill='0'),
  print ""

while True:
  data = rfm.ReceivePacket(60)
  zcount = 0
  bindata = []
  binval = 0
  binmask = 0x80
  for d in data[0]:
    rawmask = 0x80
    while (rawmask > 0) and (len(bindata) < 8):
      if (d & rawmask) > 0:
        if zcount == 1:
          binval |= binmask
          binmask >>= 1 
          
        if zcount == 5:
          binmask >>= 1
          
        if zcount == 11:
          print "Received pause"

        if zcount == 41:
          print "SYNC"
            
        zcount = 0
      else:
        zcount += 1
      rawmask >>= 1
      
      if binmask == 0:
        bindata.append(binval)
        binmask = 0x80
        binval = 0
    
    if len(bindata) == 8:
      decode(bindata)
      break;  
  
