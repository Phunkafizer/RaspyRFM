#!/usr/bin/env python3

from raspyrfm import *

d = rfmbase.RfmBase.scan()
if len(d) == 0:
	print("Unable to open SPI. Check if SPI is enabled!")
	exit

for i in range(len(d)):
	line = "Module #" + str(i + 1) + " on CS " + str(i) + ": "
	if d[i] == None:
		print(line + "No module found")
		continue

	elif d[i] == 0x24:
		line += "Found RFM69 / SX1231"

	elif d[i] == 0x12:
		line += "Found RFM95/96 / SX1276"
	else:
		line += "Found unknown module"

	print(line + " (" + hex(d[i]) + ")")

exit()

if raspyrfm_test(2, RFM69):
	print("Found RaspyRFM twin")
	rfm = RaspyRFM(2, RFM69) #when using the RaspyRFM twin
elif raspyrfm_test(1, RFM69):
	print("Found RaspyRFM single")
	rfm = RaspyRFM(1, RFM69) #when using a single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

