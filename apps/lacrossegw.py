#!/usr/bin/env python2.7

from raspyrfm import *
import sensors
from sensors import rawsensor
import sys
import time
import threading
import math
import json
from datetime import datetime
import os

nodes = {
	"0": "Kuehlschrank",
	"18": "Eisfach",
	"c0": "Kueche",
	"b0": "Kinderzimmer",
	"4c": "Aussen",
	"1c": "Aussen 2",
	"54": "Schlafzimmer",
	"70": "Wohnzimmer",
	"a8": "Treppenhaus",
	"e0": "Badezimmer",
	"f0": "MuFu",
	"f8": "Musikzimmer"
}

if raspyrfm_test(2, RFM69):
	print("Found RaspyRFM twin")
	rfm = RaspyRFM(2, RFM69) #when using the RaspyRFM twin
elif raspyrfm_test(1, RFM69):
	print("Found RaspyRFM single")
	rfm = RaspyRFM(1, RFM69) #when using a single single 868 MHz RaspyRFM
else:
	print("No RFM69 module found!")
	exit()

try:
	from influxdb import InfluxDBClient
	influxClient = InfluxDBClient(host='localhost', port=8086, username='admin', password='admin')
	influxClient.switch_database("sensors")
	influxClient.get_list_measurements()
except:
	influxClient = None
	print("influx init error")

try:
	import paho.mqtt.client as mqtt
	mqttClient = mqtt.Client()
	mqttClient.connect("localhost", 1883, 60)
	mqttClient.loop_start()
except:
	mqttClient = None
	print("mqtt init error")

rfm.set_params(
    Freq = 868.300, #MHz center frequency
    Datarate = 9.579, #kbit/s baudrate
    ModulationType = rfm69.FSK, #modulation
    Deviation = 30, #kHz frequency deviation OBW = 69.6/77.2 kHz, h = 6.3/3.5
    SyncPattern = [0x2d, 0xd4], #syncword
    Bandwidth = 100, #kHz bandwidth
        #AfcBandwidth = 150,
	#AfcFei = 0x0E,
    RssiThresh = -100, #-100 dB RSSI threshold
)

class BaudChanger(threading.Thread):
	baud = False
	def __init__(self):
		threading.Thread.__init__(self)

	def run(self):
		while True:
			time.sleep(15) 
			print "Change"
			if self.baud:
				rfm.set_params(Datarate = 9.579)
			else:
				rfm.set_params(Datarate = 17.241)
			self.baud = not self.baud

baudChanger = BaudChanger()
baudChanger.daemon = True
baudChanger.start()

def writeInflux(payload):
	if not influxClient:
		return
	T = payload["T"]
	wr = {
		"measurement": "lacrosse",
		"fields": {
			"T": T
		},
		"tags": {"sensor": payload["ID"] if not ("room" in payload) else payload["room"]}
	}

	if ("RH" in payload):
		wr["fields"]["RH"] = payload['RH']
		wr["fields"]["DEW"] = payload["DEW"]
		wr["fields"]["AH"] = payload["AH"]
		wr["fields"]["RSSI"] = payload["rssi"]
		wr["fields"]["AFC"] = payload["afc"]

	influxClient.write_points([wr])

time.sleep(4)
print "Waiting for sensors..."
cache = {}
while 1:
	rxObj = rfm.receive(7)

	try:
		sensorObj = rawsensor.CreateSensor(rxObj)
		sensorData = sensorObj.GetData()
		payload = {}
		payload["ID"] = sensorData["ID"]
		T = sensorData["T"][0]
		payload["T"] = T
	except:
		continue

	payload["rssi"] = rxObj[1]
	payload["afc"] = rxObj[2]
	payload["batlo"] = sensorData['batlo']
	payload["init"] = sensorData["init"]
	if (sensorData['ID'] in nodes):
		payload["room"] = nodes[sensorData['ID']]
	else:
		print("Unnassigned sensor:")


	if 'RH' in sensorData:
		RH = int(sensorData['RH'][0])
		payload["RH"] = RH
		a = 7.5
		b = 237.4
		SDD = 6.1078 * 10**(a*T/(b+T))

		DD = RH / 100.0 * SDD
		v = math.log10(DD/6.1078)
		payload["DEW"] = round(b*v/(a-v), 1)
		payload["AH"] = round(10**5 * 18.016/8314.3 * DD/(T+273.15), 1)

		DD = RH / 80.0 * SDD
		v = math.log10(DD/6.1078)
		payload["DEW80"] = round(b*v/(a-v), 1)

		DD = RH / 60.0 * SDD
		v = math.log10(DD/6.1078)
		payload["DEW60"] = round(b*v/(a-v), 1)


	if not payload["ID"] in cache:
		cache[payload["ID"]] = {}
		cache[payload["ID"]]["count"] = 1
	cache[payload["ID"]]["payload"] = payload;
	cache[payload["ID"]]["ts"] = datetime.now();
	cache[payload["ID"]]["count"] += 1

	os.system('clear');
	print("|ID|    ROOM    |     TIMESTAMP     |COUNT| RSSI| AFC |BAT|INI|  T  |RH| AH | DEW | TF80| TF60|")
	for key in cache:
		line = "|";
		s = cache[key]
		p = cache[key]["payload"]
		line += '{:2}|'.format(key)
		line += '{:12}|'.format("" if (not "room" in p) else p["room"][:12])
		line += s["ts"].strftime("%Y-%m-%d %H:%M:%S|")
		line += '{:5}'.format(s["count"]) + '|'
		line += '{:5}'.format(p["rssi"]) + '|'
		line += '{:5}'.format(p["afc"]) + '|'
		line += "LO!|" if p["batlo"] else "OK |"
		line += " ! |" if p["init"] else "   |"
		line += '{:5}|'.format(p["T"])
		if "RH" in p:
			line += '{:2}|'.format(p["RH"])
			line += '{:4}|'.format(p["AH"])
			line += '{:5}|'.format(p["DEW"])
			line += '{:5}|'.format(p["DEW80"])
			line += '{:5}|'.format(p["DEW60"])
		else:
			line += '--|----|-----|-----|-----|'
		print(line)

	print(payload)

	try:
		if influxClient:
			writeInflux(payload)
	except:
		pass

	try:
		if mqttClient:
			mqttClient.publish('home/lacrosse/'+ payload['ID'], json.dumps(payload))
	except:
		pass
