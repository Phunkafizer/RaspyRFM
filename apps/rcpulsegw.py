#!/usr/bin/env python

from re import split
from raspyrfm import *
import rcprotocols
import json
from argparse import ArgumentParser
import apiserver
import time
import os

MQTT_BASE_TOPIC = "home/rcpulse"

try:
    import paho.mqtt.client as mqtt
    mqttClient = mqtt.Client()
except:
	mqttClient = None
	print("mqtt init error")

parser = ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
args = parser.parse_args()

script_dir = os.path.dirname(os.path.realpath(__file__))
with open(script_dir + "/rcpulsegw.conf") as jfile:
	config = json.load(jfile)

def rccb(dec, train):
	payload = None
	if dec is None:
		payload = {"raw": train}
	else:
		if len(dec) > 0:
			payload = {"decode": dec, "raw": train}

	if payload is not None:
		print("RX", payload)
		try:
			apisrv.send(payload)
		except:
			pass

def statecb(topic, msg):
	if mqttClient:
		topic = MQTT_BASE_TOPIC + "/" + topic
		mqttClient.publish(topic, msg, 0, True)
		print("STATE CB", topic, msg)

if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

cb = rccb
rctrx = rcprotocols.RcTransceiver(args.module, args.frequency, cb, statecb)

def apicb(data):
	print("TX from API: " + str(data))
	try:
		rctrx.send(data["protocol"], data["params"])
	except:
		pass

p = config["apiport"] if "apiport" in config else 1989
apisrv = apiserver.ApiServer(p, apicb)

def on_connect(client, userdata, flags, rc):
	print("Connected with result code "+str(rc))
	client.subscribe(MQTT_BASE_TOPIC + "/#")

def on_message(client, userdata, msg):
	tl = msg.topic.split("/")
	tl = tl[len(MQTT_BASE_TOPIC.split("/")):]
	if (len(tl) < 2) or (tl[-1] != "set"):
		return
	proto = tl[0]
	tl = tl[1:-1] + [msg.payload.decode()]
	print("TX from MQTT: " + proto + " " + str(tl))
	rctrx.send(proto, tl)


if mqttClient:
	mqttClient.on_connect = on_connect
	mqttClient.on_message = on_message
	mqttClient.username_pw_set(
		config["mqtt"]["user"] if ("mqtt" in config) and ("user" in config["mqtt"]) else "",
		config["mqtt"]["pass"] if ("mqtt" in config) and ("pass" in config["mqtt"]) else None,
	)
	mqttClient.connect(
		config["mqtt"]["server"] if ("mqtt" in config) and ("server" in config["mqtt"]) else "127.0.0.1",
		config["mqtt"]["port"] if ("mqtt" in config) and ("port" in config["mqtt"]) else 1883,
		30
	)
	mqttClient.loop_start()

while True:
	time.sleep(1)
