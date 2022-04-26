#!/usr/bin/env python

from raspyrfm import *
import time

'''
use MODULE = 1 for a single raspyrfm or 1st (433 MHz) module on a raspyrfm-twin
use MODULE = 2 for the 2nd (868 MHz) module on a raspberry-twin
'''
MODULE = 1

FREQ = 433.92

rfm = RaspyRFM(MODULE, RFM69)
if rfm == None:
	print("No RFM69 module found!")
	exit()

rfm.set_params(
	Freq = FREQ, #MHz center frequency
	Datarate = 4.8, #kbit/s baudrate
	ModulationType = rfm69.FSK, #modulation
	Deviation = 30, #kHz frequency deviation
	SyncPattern = [0x93, 0x0B, 0x51, 0xDE], #syncword
	Bandwidth = 150, #kHz bandwidth
	RssiThresh = -90, #dBm RSSI threshold
	AesKey = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
)
