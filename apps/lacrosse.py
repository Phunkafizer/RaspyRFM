#!/usr/bin/env python

from raspyrfm import *
import rfmparam
import sensors
import sys, time, threading, argparse

rfm = None

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=0)
args = parser.parse_args()
mutex = threading.Lock()
event = threading.Event()
event.set()

if args.module > 0:
	rfm = RaspyRFM(args.module, RFM69)
else:
	rfm = RaspyRFM(2, RFM69) # first try module #2
	if rfm == None:
		rfm = RaspyRFM(1, RFM69) # then try module #1

if rfm == None:
	print("No RFM69 module found!")
	exit()

rfm.set_params(
	Freq = 868.30, # MHz center frequency
	ModulationType = rfm69.FSK, #modulation
	Datarate = 9.579, # kbit/s baudrate
	SyncPattern = [0x2d, 0xd4],
	Bandwidth = 250, #kHz bandwidth
	RssiThresh = -110, #dBm RSSI threshold
)

paramChanger = rfmparam.ParamChanger(rfm, event, mutex,
    [
        rfmparam.PARAM_TX35,
        rfmparam.PARAM_TX29,
        #rfmparam.PARAM_BRESSER,
        #rfmparam.PARAM_EC3K
    ]
)

while 1:
	event.wait()
	mutex.acquire()
	rxdata = rfm.receive(paramChanger.rxLen())
	mutex.release()

	if rxdata == None:
		continue

	obj = sensors.decode(rxdata)
	if obj:
		print(obj)
	else:
		print('<unknown>', rxdata)
