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
import threading
import rcprotocols

parser = ArgumentParser()
parser.add_argument("-t", "--timebase", type=int, help=u"timebase in \u03bcs")
parser.add_argument("-r", "--repeats", type=int, help=u"number of repetitions")
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
parser.add_argument("-p", "--protocol", help=u"Protocol for sending")
parser.add_argument("-w", "--write", help=u"write wavefile")
args, remainargs = parser.parse_known_args()

txdata = None
if len(remainargs) > 0:
	txdata = rcprotocols.encode(args.protocol, remainargs)

	if txdata is None:
		print("invalid code!")
		exit()

if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

rfm = RaspyRFM(args.module, RFM69)
rfm.set_params(
	Freq = args.frequency, #MHz
	Datarate = 20.0, #kbit/s
	Bandwidth = 300, #kHz
	SyncPattern = [],
	RssiThresh = -105, #dBm
	ModulationType = rfm69.OOK,
	OokThreshType = 1, #peak thresh
	OokPeakThreshDec = 3,
	Preamble = 0,
	TxPower = 13
)

if txdata:
	rfm.set_params(
		SyncPattern = [],
		Datarate = 1000.0 / (args.timebase if args.timebase else txdata[1])
	)
	rep = (args.repeats if args.repeats else txdata[2])
	rfm.send(txdata[0] * rep)
	print("Code sent!")
	exit()

trainbuf = []

class RxThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)

	def __rxcb(self, rfm):
		bit = False
		cnt = 1
		train = []
		if args.write:
			wf = wave.open(args.write, "wb")
			wf.setnchannels(1)
			wf.setsampwidth(1)
			wf.setframerate(20000)
		else:
			wf = None

		while True:
			fifo = rfm.read_fifo_wait(64)
			ba = bytearray()

			for b in fifo:
				mask = 0x80
				while mask != 0:
					if (b & mask) != 0:
						ba.append(245)
					else:
						ba.append(10)

					if ((b & mask) != 0) == bit:
						cnt += 1
					else:
						if cnt < 3: #<150 us
							train *= 0 #clear
						elif cnt > 50:
							if not bit:
								train.append(cnt)
								if len(train) > 20:
									trainbuf.append(list(train))
							train *= 0 #clear
						elif len(train) > 0 or bit:
							train.append(cnt)
						cnt = 1
						bit = not bit
					mask >>= 1

			if wf:
				wf.writeframesraw(ba)
				wf.writeframes('')

	def run(self):
		rfm.start_receive(self.__rxcb)

rxthread = RxThread()
rxthread.daemon = True
rxthread.start()

while True:
	time.sleep(0.1)
	if len(trainbuf) > 0:
		train = trainbuf.pop()
		for i, v in enumerate(train):
			train[i] = v * 50

		rcprotocols.decode(train)
