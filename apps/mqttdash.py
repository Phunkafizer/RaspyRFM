#!/usr/bin/env python

import rcprotocols
import time
import paho.mqtt.client as mqtt

mqttClient = mqtt.Client()
mqttClient.connect("localhost", 1883, 60)
mqttClient.loop_start()

def publish(proto, params):
	print("Publish: " + str(proto) + " / " + params)
	mqttClient.publish("home/rcbuttons/" + proto, params)

def rxcb(dec, train):
	if dec is None:
		print("raw", train)
		return
	for d in dec:
		publish(d["protocol"], str(d["params"]))
		
rctrx = rcprotocols.RcTransceiver(1, 433.92, rxcb)

while True:
	time.sleep(1)
