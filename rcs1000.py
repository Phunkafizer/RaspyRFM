#!/usr/bin/env python2.7

import xx2262
import sys
import re

def usage():
    print "usage:", sys.argv[0], "<5xDIPSWITCH> <CHANNEL 1-4> on|off"
    print "Example:", sys.argv[0], "brennenstuhl 00101 2 on"
    sys.exit(1)

if len(sys.argv) != 4:
    usage()

str = ''

if re.match('[01]{5}$', sys.argv[1]) is None:
    print "Invalid dipswitches"
    usage()

for c in sys.argv[1]:
    if c == '1':
        str += '0'
    else:
        str += 'F'

if re.match('[1-4]$', sys.argv[2]) is None:
    print "Invalid channel"
    usage()

ch = ord(sys.argv[2][0]) - ord('1')
for i in range(4):
    if i == ch:
        str += '0'
    else:
        str += 'F'

str += 'FF'

if sys.argv[3] == 'on':
  str += 'F'
else:
  str += '0'
  
print "Sending", str

data = xx2262.MakeFrame(str, 8)
xx2262.rfm.SendPacket(data)
