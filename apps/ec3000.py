#!/usr/bin/env python

from raspyrfm import *
import sys
import time

try:
	from influxdb import InfluxDBClient
	influxClient = InfluxDBClient(host='raspberrypi', port=8086, username='admin', password='admin')
	influxClient.switch_database("sensors")
	influxClient.get_list_measurements()
except:
	influxClient = None
	print("influx init error")

if raspyrfm_test(2, RFM69):
	print("Found RaspyRFM twin")
	rfm = RaspyRFM(2, RFM69) #when using the RaspyRFM twin
elif raspyrfm_test(1, RFM69):
	print("Found RaspyRFM single")
	rfm = RaspyRFM(1, RFM69) #when using a single single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

rfm.set_params(
	Freq = 868.300, #MHz center frequency
	Datarate = 20, #kbit/s baudrate
	ModulationType = rfm69.FSK, #modulation
	Deviation = 20, #kHz frequency deviation
	SyncPattern = [0x13, 0xF1, 0x85, 0xD3, 0xAC], #syncword
	Bandwidth = 200, #kHz bandwidth
)

data = []

def lshift(datain):
	datain.append(0)
	for i in range(len(datain) - 1):
		datain[i] = ((datain[i] << 4) | (datain[i + 1] >> 4)) & 0xFF
	del datain[-1]
	return datain

def calccrc(datain):
	crc = 0xFFFF
	for d in datain:
		d ^= crc & 0xFF
		d = (d ^ (d << 4)) & 0xFF
		crc = ((d << 8) | (crc >> 8)) ^ (d >> 4) ^ (d << 3)
	return crc

def unstuffrev(datain):
	cnt1bits = 0
	obi = 0
	oby = 0
	result = []
	for b in datain:
		for ibi in range(8):
			bit = b & 0x80
			b <<= 1
			if (cnt1bits >= 5) and (bit == 0):
				cnt1bits = 0
				continue
			if (bit > 0):
				cnt1bits += 1
			else:
				cnt1bits = 0
			oby >>= 1
			oby |= bit
			obi += 1
			if (obi == 8):
				obi = 0
				result.append(oby)
				oby = 0
	if obi > 0:
		result.append(oby >> (8 - obi))

	return result


def count1bits(value):
	c = 0
	while (value > 0):
		c += 1
		value &= value - 1
	return c

def descramble(datain):
	dataout = []
	lfsr = 0xF185D3AC
	outbyte = 0
	for b in datain:
		inb = b
		for bit in range(8):
			inbit = (inb & 0x80) >> 7
			outbit = inbit ^ (count1bits(lfsr & 0x31801) & 0x01)
			lfsr = lfsr << 1 | inbit
			inb <<= 1
			outbyte = outbyte << 1 | outbit
		dataout.append((outbyte ^ 0xFF) & 0xFF)
	return dataout

def showhex(title, data):
	str = ""
	for d in data:
		str += hex(d) + ", "
	print(title + ": " + str)

def calcword(datain):
	result = 0
	for d in datain:
		result <<= 8
		result |= d
	return result

print("Waiting for sensors...")
while 1:
	data = rfm.receive(56)
	data = descramble(data[0])
	data = unstuffrev(data[1:])
	crc = calccrc(data[:41])
	if crc == 0xf0b8:
		data = lshift(data)
		payload = {}
		payload["ID"] = calcword(data[0:2])
		th = calcword(data[29:31])
		tl = calcword(data[2:4])
		payload["T"] = (th << 12) | tl #s
		th = calcword(data[35:37])
		tl = calcword(data[6:8])
		payload["Ton"] = (th << 12) | tl #s
		payload["P"] = calcword(data[15:17]) / 10.0 #W
		payload["Pmax"] = calcword(data[17:19]) / 10.0 #W
		wlow = calcword(data[11:15]) & 0x0FFFFFFF
		whigh = calcword(data[33:35])
		payload["E"] = ((whigh << 28) | wlow) / 3600.0 / 1000 #kWh
		print(payload)
		if influxClient:
			wr = {}
			wr["measurement"] = "energy"
			wr["fields"] = {
				"E": payload["E"],
				"P": payload["P"]
			}
			wr["tags"] = {
				"id": payload["ID"]
			}
			influxClient.write_points([wr])
