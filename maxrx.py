#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import sys
import time
import threading

devices = {
	'0x19cf40': 'SchlafWall',
	'0x1a2a84': 'SchlafThermos',
	'0x12c400': 'SchlafThermos2',
	'0x192b8d': 'Wall2',
	'0x192765': 'Wall3',
}

if Rfm69.Test(1):
	print("Found RaspyRFM twin")
	rfm = Rfm69(1, 24) #when using the RaspyRFM twin
elif Rfm69.Test(0):
	print("Found RaspyRFM single")
	rfm = Rfm69() #when using a single single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

def CallbackSync():
	lfsr = 0x1ff
	frame = []
	frame.append(rfm.ReadFifoWait())
	len = frame[0] ^ 0xFF #invert due to whitening
	
	for i in range(len):
		frame.append(rfm.ReadFifoWait())
	
	rfm.WhitenTI(frame)
		
	x = {}
	x['cnt'] = frame[1]
	x['flag'] = hex(frame[2])
	x['type'] = hex(frame[3])
	x['src'] = hex(frame[4] << 16 | frame[5] << 8 | frame[6])
	x['dst'] = hex(frame[7] << 16 | frame[8] << 8 | frame[9])
	x['grp'] = frame[10]
	x['pay'] = []
	for i in range(len - 10):
		x['pay'].append(frame[i + 11])

	if x['src'] in devices:
		x['src'] = devices[x['src']]

	if x['dst'] in devices:
		x['dst'] = devices[x['dst']]
		
	info = ""
	if x['type'] == '0x42':
		info = str(x['pay'][0] / 2.0) + ' / ' + str(x['pay'][1] / 10.0)

	print(x['src'] + "->" + x['dst'] + " type " + x['type'] + ':', x['pay'], info)
	
rfm.SetParams(
	Freq = 868.300, #MHz center frequency
	ModulationType = rfm69.FSK, #modulation
	Datarate = 9.992, #kbit/s baudrate
	Deviation = 19.042, #kHz frequency deviation -> OBW = 48 kHz, h = 3.81
	SyncPattern = [0xc6, 0x26, 0xc6, 0x26], #syncword
	Bandwidth = 100, #kHz bandwidth (101.5)
	RssiThresh = -100, #-100 dB RSSI threshold
	CallbackSync = CallbackSync
)

print "Waiting for sensors..."

while 1:
	data = rfm.ReceivePacket(64)