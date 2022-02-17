#!/usr/bin/env python

import sys, time, wave, struct, threading, argparse
from raspyrfm import *
import rcprotocols

parser = argparse.ArgumentParser()
parser.add_argument("-t", "--timebase", type=int, help=u"timebase in \u03bcs")
parser.add_argument("-r", "--repeats", type=int, help=u"number of repetitions")
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
parser.add_argument("-p", "--protocol", help=u"Protocol for sending")
args, remainargs = parser.parse_known_args()

def rxcb(dec, train):
	if dec is None:
		print("raw", train)
		return
	for d in dec:
		print(d)

if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

rctrx = rcprotocols.RcTransceiver(args.module, args.frequency, rxcb)

if args.protocol:
	proto = rcprotocols.get_protocol(args.protocol)
	if proto:
		parser2 = argparse.ArgumentParser()
		for param in proto._params:
			parser2.add_argument("-" + param[0], "--" + param[1], required=True)
		params = parser2.parse_args(remainargs)
		rctrx.send(args.protocol, params.__dict__, args.timebase, args.repeats)
	else:
		print("Unknown protocol.")
	del rctrx
	exit()

print("Listening...")
while (1):
	time.sleep(1)
