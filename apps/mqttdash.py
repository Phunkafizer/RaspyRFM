#!/usr/bin/env python2.7

import rcprotocols
import time
import paho.mqtt.client as mqtt

mqttClient = mqtt.Client()
mqttClient.connect("localhost", 1883, 60)
mqttClient.loop_start()

rx = rcprotocols.PulseReceiver(1)

lastEvents = {}

def publish(proto, code):
	print("Publish: " + str(proto) + " / " + str(code))
	mqttClient.publish("home/rcbuttons/" + proto, code)

while True:
	time.sleep(0.1)
	evts = rx.getEvents()
	if evts:
		for e in evts:
			if e["protocol"] in lastEvents:
				le = lastEvents[e["protocol"]]
				if e["code"] != le["code"]:
					publish(e["protocol"], e["code"])
					le["code"] = e["code"]
				elif (time.time() - le["ts"] > 1):
					publish(e["protocol"], e["code"])
				le["ts"] = time.time()
			else:
				lastEvents[e["protocol"]] = {
					"ts": time.time(),
					"code": e["code"]
				}
				publish(e["protocol"], e["code"])
