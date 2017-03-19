#!/usr/bin/env python2.7

import rfm69
import sensors
from sensors import rawsensor
import time
import requests
import json


URL = 'https://emoncms.org/input/post.json'
APIKEY = '12345678901234567890'

sensors = [
	{
		"sensorId": 'b8', #ID of the sensor
		"minInterval": 30, #if new value received before <minInterval> in seconds, value is discarded
		"node": 1 #node number in emoncms
	},
	{
		"sensorId": 'e4',
		"minInterval": 30,
		"node": 2
	},
	{
		"sensorId": 'ec',
		"minInterval": 30,
		"node": 3
	},
  {
		"sensorId": '68',
		"minInterval": 30,
		"node": 4
	},
  {
		"sensorId": '4',
		"minInterval": 30,
		"node": 5
	},
  {
		"sensorId": '78',
		"minInterval": 30,
		"node": 6
	}	
]

lasttimes = {}

def LogSensor(data):
    for s in sensors: #search for received sensor in list
        if s['sensorId'] == data['ID']:
            if data['ID'] in lasttimes:
                if time.time() - lasttimes[data['ID']] < s['minInterval']:
                    print "discarded value"
                    return
            lasttimes[data['ID']] = time.time() 

            values = {}
            values['T'] = data['T'][0]
            if 'RH' in data:
                values['RH'] = data['RH'][0]

            payload = {'apikey': APIKEY, 'node': s['node'], 'json': json.dumps(values)}
            r = requests.get(URL, params = payload)
            print "Sending to emon:", payload, "Result:", r
            return
    print "No match for ID"

rfm = rfm69.Rfm69()

rfm.SetParams(
    Freq = 868.300, #MHz center frequency
    Datarate = 9.579, #17.241, #kbit/s baudrate
    Deviation = 30, #30 kHz
    ModulationType = rfm69.FSK, #modulation
    SyncPattern = [0x2d, 0xd4], #syncword
    Bandwidth = 100, #kHz bandwidth
    AfcBandwidth = 150, #kHz AFC bandwidth
    LnaGain = 0x88,
    RssiThresh = -100, #dBm
    AfcFei = 0x00 #AfcAutoOn
    )
    
while 1:
    data = rfm.ReceivePacket(7)
    obj = rawsensor.CreateSensor(data)
    print(str(obj))
    if len(obj._data) > 0:
       LogSensor(obj._data) 
