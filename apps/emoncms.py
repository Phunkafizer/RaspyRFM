#!/usr/bin/env python

import time, requests, json, argparse
from raspyrfm import *
import sensors
from sensors import rawsensor

URL = 'https://emoncms.org/input/post.json'
APIKEY = '123456789123456789'

sensors = [
	{
		"sensorId": '68', #ID of the sensor
		"minInterval": 30, #if new value received before <minInterval> in seconds, value is discarded
		"node": 1 #node number in emoncms
	},
	{
		"sensorId": '8',
		"minInterval": 30,
		"node": 2
	},
	{
		"sensorId": '98',
		"minInterval": 30,
		"node": 3
	},
  {
		"sensorId": '18',
		"minInterval": 30,
		"node": 4
	}
]

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=0)
args = parser.parse_args()

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

lasttimes = {}

def LogSensor(data):
    if not ('ID' in data):
        return

    for s in sensors: #search for received sensor in list
        if s['sensorId'] == data['ID']:
            if data['ID'] in lasttimes:
                if time.time() - lasttimes[data['ID']] < s['minInterval']:
                    print("discarded value")
                    return
            lasttimes[data['ID']] = time.time() 

            values = {}
            values['T'] = data['T'][0]
            if 'RH' in data:
                values['RH'] = data['RH'][0]

            payload = {'apikey': APIKEY, 'node': s['node'], 'json': json.dumps(values)}
            r = requests.get(URL, params = payload)
            print("Sending to emon:", payload, "Result:", r)
            return
    print("No match for ID")

    
while 1:
    data = rfm.receive(7)
    obj = rawsensor.CreateSensor(data)
    print(str(obj))
    if len(obj._data) > 0:
       LogSensor(obj._data) 
