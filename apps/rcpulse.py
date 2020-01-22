#!/usr/bin/env python2.7

import RaspyRFM
import sys
import time
import it32
import tristate
import bistate24
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-t", "--timebase", type=int, help=u"timebase in \u03bcs")
parser.add_argument("-r", "--repeats", type=int, help=u"number of repetitions")
parser.add_argument("code", nargs='*', help="code, e. g. '000000000FFF', 'A 1 2 on' or '10111100011101011111111110001110'")
args = parser.parse_args()

protos = [
	it32,
	tristate,
	bistate24,
]

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

rfm = RaspyRFM.RaspyRFM()
rfm.SetParams(
	Freq = 433.92, #MHz
	Datarate = 20.0, #kbit/s
	Bandwidth = 200, #kHz
	SyncPattern = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F],
	RssiThresh = -105, #dBm
	ModulationType = RaspyRFM.OOK,
	OokThreshType = 1, #peak thresh
	OokPeakThreshDec = 3,
)

if txdata:
	rfm.SetParams(
		SyncPattern = [],
		Datarate = 1000.0 / (args.timebase if args.timebase else txdata[2])
	)
	rep = (args.repeats if args.repeats else txdata[1])
	rfm.SendPacket(txdata[0] * rep)
	print("Code sent!")
	exit()
	
def Decode(pulses):
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
	data = rfm.ReceivePacket(260)
	s = ""

	pulsecount = 7
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
