#!/usr/bin/env python2.7

from raspyrfm import *
import sys
import time
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-t", "--timebase", type=int, help=u"timebase in \u03bcs")
parser.add_argument("-r", "--repeats", type=int, help=u"number of repetitions")
parser.add_argument("code", nargs='*', help="code, e. g. '000000000FFF', 'A 1 2 on' or '10111100011101011111111110001110'")
args = parser.parse_args()

txdata = None
if len(args.code) > 0:
	txdata = None
	for proto in protos:
		data = proto.Encode(args.code)
		if data:
			txdata = data
			break

	if txdata is None:
		print("invalid code!")
		exit()

rfm = RaspyRFM(1, RFM69)
rfm.set_params(
	Freq = 868.35, #MHz
	Datarate = 20.0, #kbit/s
	Bandwidth = 200, #kHz
	SyncPattern = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07],
	RssiThresh = -105, #dBm
	ModulationType = rfm69.OOK,
	OokThreshType = 1, #peak thresh
	OokPeakThreshDec = 3,
)

if txdata:
	rfm.SetParams(
		SyncPattern = [],
		Datarate = 5.0
	)
	rep = (args.repeats if args.repeats else txdata[1])
	rfm.SendPacket(txdata[0] * rep)
	print("Code sent!")
	exit()

def Decode(pulses):
	if len(pulses) != 118:
		return;

	b = ""
	for p in pulses:
		if (p>=6) and (p<=10):
			b += "s"
		elif (p > 10) and (p<15):
			b += "l"
		else:
			b += '?'
	s = ""
	while len(b) > 0:
		if b[:2] == 'ss':
			s += '0'
		elif b[:2] == 'll':
			s += '1'
		else:
			s += '?'
		b = b[2:]
	print(s)
	print("SYNC " + s[1:13] + " HC1 " + s[13:22] + " HC2 " + s[22:31] + 
		" ADR " + s[31:40])
	return
	for i in range(len(pulses)):
		pulses[i] *= 50

	dec = None
	for proto in protos:
		dec = proto.Decode(pulses)
		if dec:
			print(dec)

	if not dec:
		print("Len " + str(len(pulses)) + ": " + str(pulses))

while True:
	data = rfm.receive_packet(400)
	s = ""

	pulsecount = 3
	glitchcount = 0
	bit = True
	pulses = []

	for d in data[0]:
		s += format(d, '08b')
		mask = 0x80
		while mask > 0:
			newbit = (d & mask) > 0

			if glitchcount > 0:
				glitchcount += 1
				if newbit == bit:
					pulsecount += glitchcount
					glitchcount = 0
				else:
					if glitchcount == 3:
						pulses.append(pulsecount)
						if pulsecount > 50:
							Decode(pulses)
							pulses = []
						bit = newbit
						pulsecount = 3
						glitchcount = 0
			else:
				if newbit == bit:
					pulsecount += 1
				else:
					glitchcount = 1

			mask >>= 1
