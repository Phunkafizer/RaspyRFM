#!/usr/bin/env python2.7

import xx2262
import sys
import re

def encodeBits(val, num, pol, inv):
    result = ''
    for i in range(num):
        if (val & 0x01) ^ inv:
            result += 'F'
        else:
            result += pol
        val >>= 1
    return result

def usage():
    print "usage: intertechno <HOUSECODE A-P> <GROUP 1-4> <CHANNEL 1-4> on|off" #12-digit code 12 * ['0' | '1' | 'f']
    print "Example: intertechno A 1 1 on"
    sys.exit(1)

if len(sys.argv) != 5:
    usage()

itstr = ''

if re.match('[A-P]$', sys.argv[1]) is None:
    print "Invalid housecode"
    usage()

housecode = ord(sys.argv[1][0]) - ord('A')
itstr += encodeBits(housecode, 4, '0', False)

if re.match('[1-4]$', sys.argv[3]) is None:
    print "Invalid channel"
    usage()

ch = ord(sys.argv[3][0]) - ord('1')
itstr += encodeBits(ch, 2, '0', False)

if re.match('[1-4]$', sys.argv[2]) is None:
    print "Invalid group"
    usage()

group = ord(sys.argv[2][0]) - ord('1')
itstr += encodeBits(group, 2, '0', False)

itstr += '0F'

if sys.argv[4] == 'on':
  itstr += 'FF'
else:
  itstr += 'F0'
  
print "Sending", itstr

data = xx2262.MakeFrame(itstr, 8)
xx2262.rfm.SendPacket(data)
