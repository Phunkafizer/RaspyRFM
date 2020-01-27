#!/usr/bin/env python2.7

from raspyrfm import *
import sys
import time
import it32
import tristate
import bistate24
import fs20
from argparse import ArgumentParser
import wave, struct

parser = ArgumentParser()
parser.add_argument("-t", "--timebase", type=int, help=u"timebase in \u03bcs")
parser.add_argument("-r", "--repeats", type=int, help=u"number of repetitions")
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
parser.add_argument("-w", "--write", help=u"write wavefile")
parser.add_argument("code", nargs='*', help="code, e. g. '000000000FFF', 'A 1 2 on' or '10111100011101011111111110001110'")
args = parser.parse_args()

protos = [
	it32,
	tristate,
	bistate24,
	fs20,
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

rfm = RaspyRFM(args.module, RFM69)
rfm.set_params(
	Freq = args.frequency, #MHz
	Datarate = 20.0, #kbit/s
	Bandwidth = 200, #kHz
	SyncPattern = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F],
	RssiThresh = -105, #dBm
	ModulationType = rfm69.OOK,
	OokThreshType = 1, #peak thresh
	OokPeakThreshDec = 3,
	Preamble = 0,
	TxPower = 13
)

wf = wave.open("out.wav", "wb")
def rxcb():
	while True:
		d = rfm.read_fifo_wait(64)
		ba = bytearray()
		for s in d:
			mask = 0x80
			while mask > 0:
				if (s & mask) > 0:
					ba.append(255)
				else:
					ba.append(0)
				mask >>= 1
		wf.writeframesraw(ba)
			
if args.write:
	wf.setnchannels(1)
	wf.setsampwidth(1)
	wf.setframerate(20000)
	
	rfm.set_params(
		SyncPattern = [],
		OokThreshType = 0, #fix thresh
		OokFixedThresh = 85,
	)
	rfm.start_rx(rxcb)
	
	wf.writeframes('')
	wf.close()
	print("WRITE!")
	exit()

rfm.set_params(
	SyncPattern = [],
	Datarate = 1.63,
)
i=[
	"01010011110011111110000111111111",
	"01011101110011111110000111111111",
	"01100011110011111110000111111111",
	"01101101110011111110000111111111",
]
do=[]
b=0
db=0
def addpulse(h, l):
	global do, b, db
	for i in range(h):
		db <<= 1
		db |= 1
		b += 1
		
		if b == 8:
			do.append(db)
			db = 0
			b = 0
			
	for i in range(l):
		db <<= 1	
		b += 1
		
		if b == 8:
			do.append(db)
			db = 0
			b = 0

for c in i[args.timebase]:
	if c == '0':
		addpulse(2, 1)
	else:
		addpulse(1, 2)
addpulse(1, 17)
#print(do, b)
rfm.send_packet(do * 3)
exit() 	 

rfm.set_params(
	Datarate = 20.0, #kbit/s
	SyncPattern = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0F],
)	

if txdata:
	rfm.set_params(
		SyncPattern = [],
		Datarate = 1000.0 / (args.timebase if args.timebase else txdata[2])
	)
	rep = (args.repeats if args.repeats else txdata[1])
	rfm.send_packet(txdata[0] * rep)
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
			
	s = ""
	if len(pulses) == 66:
		for p in pulses:
			if (p>900):
					s += "l"
			else:
					s += "s"
	b = ""
	while len(s) > 0:
		if s[:2] == "sl":
			b += "1"
		elif s[:2] == "ls":
			b += "0"
		else:
			b += "?"
		s = s[2:]
	#print(b)
					
	#print(len(pulses), pulses)

	#if not dec:
	#	print("Len " + str(len(pulses)) + ": " + str(pulses))

while True:
	data = rfm.receive_packet(260)
	s = ""

	pulsecount = 4
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
