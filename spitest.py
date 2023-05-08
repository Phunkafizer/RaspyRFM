#!/usr/bin/env python

import RPi.GPIO as GPIO
import spidev
import random

spi = spidev.SpiDev()
spi.open(0, 0)

random.seed()

dataout = []

for i in range(32):
	dataout.append(random.randint(0, 255))

print("Transfering testdata"), dataout
datain = spi.xfer2(dataout)

if dataout == datain:
	print("Received data OK!")

spi.close()
