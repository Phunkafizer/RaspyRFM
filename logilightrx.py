#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sys
import time
#import types
#import os

rfm = Rfm69()
rfm.SetParams(
    Freq = 433.92,
    Datarate = 1 / 275E-06 / 1000,
    Bandwidth = 4000,
    SyncPattern = [0x80, 0x00, 0x00, 0x00],
    RssiThresh = -80,
    ModulationType = rfm69.OOK
    )

def Decode(bitpos, data):
  frame = 0 #space for decoded logilink frame
  for i in range(bitpos, bitpos + 24 * 4, 4):
    bitpattern = (data[i / 8] << 8) | (data[i / 8 + 1])
    bitpattern <<= i % 8
    bitpattern &= 0xF000
    frame <<= 1
    if bitpattern == 0xe000:
      frame |= 1
    elif bitpattern == 0x8000:
      pass
    else:
      return
  systemcode = frame >> 4
  onoff = (frame >> 3) & 0x01
  ch = frame & 0x07
  return systemcode, onoff, ch

while True:
  data = rfm.ReceivePacket(60)
  zcount = 0
  binstr = ""
  bitcount = 0
  #print "received raw data:", data[0]
  sync = 0
  for bit in range(len(data[0]) * 8):
    sync <<= 1
    sync |= ((data[0][bit / 8] >> (7 - (bit % 8)))) & 0x01
    sync &= 0xFFFFFFFF
    if sync == 0x80000000: #sync found in frame
      if (bit >= 24 * 4 + 32 - 1): #logilinkframe has 24 bit, 1 logilink-bit = 4 raw-bits; + 32 raw bits sync
        res = Decode(bit - 24 * 4 - 32 + 1, data[0])
        if res is not None:
          print "Systemcode", res[0], "onoff", res[1], "ch", res[2]
