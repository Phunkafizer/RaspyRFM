#!/usr/bin/env python2.7

import rfm69
from rfm69 import Rfm69
import xx2262
import it32
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
    print "usage:"
    print "intertechno <HOUSECODE A-P> <GROUP 1-4> <CHANNEL 1-4> on|off" #12-digit code 12 * ['0' | '1' | 'f']
    print "intertechno <12 symbols tristate code>"
    print "intertechno <26 bit address> <1 goup bit> <4 bit unit> on|off"
    print "intertechno <32 bit code>"
    print "Examples:"
    print "intertechno A 1 1 on"
    print "intertechno 0000FFFF0FFF"
    print "interttechno 11110000111100001111000010 0 1110 on"
    print "interttechno 11110000111100001111000010010000"
    sys.exit(1)

if __name__ == "__main__":
	import sys
	cmd = ""
	data = None
	for i in range(1, len(sys.argv)):
		cmd += " " + sys.argv[i]
	cmd = cmd.strip()
	daatarate = None

	if re.match('^[01]{32}$', cmd) is not None:
		data = it32.MakeFrame(cmd, 5)
		datarate = 4

	if re.match('^[01]{26} [01] [01]{4} (on|off)$', cmd) is not None:
		tmp = cmd[0:26] + cmd[27]
		if cmd[-2:] == 'on':
			tmp += '1'
		else:
			tmp += '0'
		tmp += cmd[29:33]
		data = it32.MakeFrame(tmp, 5)
		datarate = 1/275E-6/1000

	if re.match('^[A-P] [1-4] [1-4] (on|off)$', cmd) is not None:
		housecode = ord(cmd[0]) - ord('A')
		itstr = ''
		itstr += encodeBits(housecode, 4, '0', False)

		ch = ord(cmd[4]) - 1
		itstr += encodeBits(ch, 2, '0', False)

		group = ord(cmd[2]) - 1
		itstr += encodeBits(group, 2, '0', False)

		itstr += '0F'

		if cmd[-2:] == 'on':
			itstr += 'FF'
		else:
			itstr += 'F0'

		data = xx2262.MakeFrame(itstr, 5)
		datarate = 2.66666666

	if re.match('^[01Ff]{12}$', cmd) is not None:
		data = xx2262.MakeFrame(cmd, 5)
		datarate = 2.66666666

if data is not None:
	rfm = Rfm69()
	rfm.SetParams(
		Freq = 433.92,
		Datarate = datarate, #2.666666,
		TXPower = 13,
		ModulationType = rfm69.OOK,
		SyncPattern = []
	)
	rfm.SendPacket(data)
else:
	usage()
