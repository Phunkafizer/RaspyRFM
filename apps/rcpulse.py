#!/usr/bin/env python2.7

from raspyrfm import *
import sys
import time
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

def rxcb(dec, train):
	for p in dec:
		print(p)
	if len(dec) == 0:
		print(train)

if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

rctrx = rcprotocols.RcTransceiver(args.module, args.frequency, rxcb)

if len(remainargs) > 0:
	rctrx.send_args(args.protocol, remainargs, args.timebase, args.repeats)
	del rctrx
	exit()

state = 1
while True:
	time.sleep(10)
	
	rctrx.send_dict({"protocol": "ittristate", "house": "A", "unit": 1, "state": state})
	if (state == 1):
		state = 0
	else:
		state = 1