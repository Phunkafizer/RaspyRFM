#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sys

if len(sys.argv) != 5:
    print "usage: logiloghttx.py <systemcode> <channel> <on/off> <repetitions>"
    print "Example: logilighttx.py 65565 7 1 4"
    sys.exit(1)

rfm = Rfm69()
rfm.SetParams(
    Freq = 433.92,
    Datarate = 2.666666,
    TXPower = 13,
    ModulationType = rfm69.OOK,
    SyncPattern = []
    )

#Frame generation
def MakeFrame(systemcode, onoff, channel, rep):
	data = systemcode << 4 | onoff << 3 | channel
	frame = [0x00] * 12
	for i in range(24):
		if (data & (0x800000>>i)):
			nibble = 0xE0
		else:
			nibble = 0x80
		frame[i / 2] |= nibble >> (4 * (i % 2))
	
	frame += [0x80, 0x00, 0x00, 0x00] #sync
        
	return frame * rep

data = MakeFrame(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
rfm.SendPacket(data)
