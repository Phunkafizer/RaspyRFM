#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, time, threading, math, json, os, argparse, shutil, re
from raspyrfm import *
import sensors
from datetime import datetime
import apiserver
import climatools
import rfmparam
import socketserver
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
from urllib.parse import urlparse, parse_qs

lock = threading.Lock()
event = threading.Event()
event.set()
rfmlock = threading.Lock()
reloadConf = True
config = {}
cache = {}

script_dir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(script_dir + "/868gw.conf"):
	if os.path.exists(script_dir + "/lacrossegw.conf"):
		shutil.move(script_dir + "/lacrossegw.conf", script_dir + "/868gw.conf")
	else:
		shutil.copyfile(script_dir + "/868gw.conf.tmpl", script_dir + "/868gw.conf")
with open(script_dir + "/868gw.conf") as jfile:
    config = json.load(jfile)
    jfile.close()

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

try:
    from influxdb import InfluxDBClient
    influxClient = InfluxDBClient(
        host=config["influxdb"]["host"],
        port=config["influxdb"]["port"],
        username=config["influxdb"]["user"],
        password=config["influxdb"]["pass"]
    )

    influxClient.switch_database(config["influxdb"]["database"])
    print("InfluxDB1 client loaded")

except Exception as ex:
    influxClient = None
    print("InfluxDB1 Exception:", ex)

influxClient2 = None
try:
    import influxdb_client
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    if config["influxdb2"]["url"] != "":
        influxClient2 = influxdb_client.InfluxDBClient(url=config["influxdb2"]["url"], token=config["influxdb2"]["token"], org=config["influxdb2"]["org"])
        influxapi = influxClient2.write_api(write_options=SYNCHRONOUS)
        print("InfluxDB2 client loaded")
except Exception as ex:
    print("InfluxDB2 Exception:", ex)

try:
    import paho.mqtt.client as mqtt
    mqttClient = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
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
except Exception as ex:
    mqttClient = None
    print("MQTT init error:", ex)

rfm.set_params(
    Freq = 868.300, # MHz center frequency
    Datarate = 9.579, # kbit/s baudrate
    ModulationType = rfm69.FSK, # modulation
    SyncPattern = [0x2d, 0xd4], # syncword
    Bandwidth = 240, # kHz
    AfcBandwidth = 200, # kHz
    #AfcFei = 0x0C, # AFC auto clear, AFC auto on
    RssiThresh = -110, # dBm RSSI threshold
)

paramChanger = rfmparam.ParamChanger(rfm, event, rfmlock,
    [
        rfmparam.PARAM_TX35,
        rfmparam.PARAM_TX29,
        rfmparam.PARAM_BRESSER,
        rfmparam.PARAM_EC3K
    ]
)

def getCachePayload(id):
    if not (id in cache) or ((datetime.now() - cache[id]["ts"]).total_seconds() > 300):
        return None

    payload = cache[id]["payload"]

    sensorConfig = None
    for csens in config["sensors"]:
        if id == csens["id"]:
            sensorConfig = csens
            break

    if sensorConfig is not None:
        payload["room"] = sensorConfig["name"]
        if 'tMax' in sensorConfig or 'tMin' in sensorConfig:
            payload["tStatus"] = "ok"

            if ('tMax' in sensorConfig) and (payload["T"] > sensorConfig["tMax"]):
                payload["tStatus"] = "high"

            if ('tMin' in sensorConfig) and (payload["T"] < sensorConfig["tMin"]):
                payload["tStatus"] = "low"

        if ('isOutside' in sensorConfig):
            payload["isOutside"] = sensorConfig['isOutside']

        if ('RH' in payload):
            outPayload = getCachePayload(sensorConfig["idOutside"]) if 'idOutside' in sensorConfig else None
            if (outPayload is not None) and ('AH' in outPayload):
                payload["AHratio"] = round((outPayload["AH"] / payload["AH"] - 1) * 100)
                payload["RHvent"] = round(outPayload["VP"] / payload["SVP"] * 100)

            if ('rhMax' in sensorConfig) and (payload["RH"] > sensorConfig["rhMax"]):
                #too wet!
                payload["rhStatus"] = "high"
                if "AHratio" in payload:
                    if payload["AHratio"] <= -10:
                        payload["window"] = "open"
                    elif payload["AHratio"] >= 10:
                        payload["window"] = "close"

            if ('rhMin' in sensorConfig) and (payload["RH"] < sensorConfig["rhMin"]):
                #too dry
                payload["rhStatus"] = "low"
                if "AHratio" in payload:
                    if payload["AHratio"] >= 10:
                        payload["window"] = "open"
                    elif payload["AHratio"] <= -10:
                        payload["window"] = "close"

            if 'rhStatus' not in payload and ('rhMin' in sensorConfig or 'rhMax' in sensorConfig):
                payload["rhStatus"] = "ok"

            if 'Tsurf' in sensorConfig:
                aw = round(climatools.calcAw(payload['T'], payload['RH'], sensorConfig['Tsurf']))
                if aw > 100:
                    aw = 100
                payload["aw"] = aw
                awWarn = sensorConfig["awWarn"] if 'awWarn' in sensorConfig else 80
                payload["awStatus"] = 'high' if aw >= awWarn else 'ok'

    return payload

class MyHttpRequestHandler(BaseHTTPRequestHandler):
    def getdata(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        resp = {"sensors": []}
        idlist = []

        lock.acquire()
        for csens in config["sensors"]:
            id = csens["id"]
            payload = getCachePayload(id)
            if payload is not None:
                idlist.append(id)
            else:
                payload = {"room": csens["name"], "id": id}
            resp["sensors"].append(payload)

        for id in cache:
            if id in idlist:
                continue

            payload = getCachePayload(id)
            if payload:
                resp["sensors"].append(payload)

        lock.release()

        self.wfile.write(json.dumps(resp).encode())

    def do_GET(self):
        url = urlparse(self.path)
        p = url.path
        q = parse_qs(url.query)
        if 'name' in q:
            name = q['name'][0]

        if p == '/data':
            self.getdata()

        elif p == '/config':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(config).encode())

        elif p == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            with open(script_dir + '/index.html', 'rb') as file:
                self.wfile.write(file.read())

        elif p == '/history' and influxClient and name:
            resp = influxClient.query(
                "SELECT mean(mean_T), mean(mean_RH) FROM rp_1w.weather WHERE (sensor = $name) AND time >= now() - 4h GROUP BY time(3m) fill(none)",
                bind_params={'name': name}
                )
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp.raw['series'][0]['values']).encode())
        else:
            return self.send_error(404, self.responses.get(404)[0])

    def do_POST(self):
        url = urlparse(self.path)
        path = url.path
        if path == '/config':
            content_len = int(self.headers.get('content-length'))
            global config
            config = json.loads(self.rfile.read(content_len))
            global script_dir
            with open(script_dir + "/868gw.conf", "w") as jfile:
                jfile.write(json.dumps(config))
                jfile.close()
            global reloadConf
            reloadConf = True
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'')


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass):
        self.allow_reuse_address = True
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate=False)
        self.server_bind()
        self.server_activate()
    pass

p = config["webport"] if "webport" in config else 8080
server = Server(('0.0.0.0', p), MyHttpRequestHandler)
server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()

p = config["apiport"] if "apiport" in config else 1991
apisrv = apiserver.ApiServer(p)

def getTopic(sensor):
    if "mqtt" in config and "basetopic" in config["mqtt"]:
        topic = config["mqtt"]["basetopic"]
    else:
        topic = "home"
    topic += "/" + sensor.getClass() + "/" + sensor.getId()
    return topic

while 1:
    if reloadConf:
        reloadConf = False
        with open(script_dir + "/868gw.conf") as jfile:
            config = json.load(jfile)
        jfile.close()
        for c in cache.values():
            c["discSent"] = False

    event.wait()
    rfmlock.acquire()
    rxData = rfm.receive(paramChanger.rxLen())
    rfmlock.release()

    if rxData == None:
        continue

    try:
        sensor = sensors.decode(rxData)
        if not sensor:
            continue
        print(sensor)
        sensorValues = sensor.getValues()
        payload = {}
        for k in sensorValues:
             payload[k] = sensorValues[k][0]

        id = sensor.getId()
        payload["id"] = id

    except Exception as e:
        print("EXCEPT!", e)
        continue

    lock.acquire()

    if not id in cache:
        cache[id] = {"discSent": False}
    cache[id]["payload"] = payload
    cache[id]["ts"] = datetime.now()

    payload = getCachePayload(id)

    apipayl = {
        "decode": [{
            "protocol": sensor.getType(),
            "params": payload,
            "class": sensor.getClass()
        }]
    }
    apisrv.send(apipayl)

    if not cache[id]["discSent"] and "room" in payload and mqttClient: # discovery not sent yet & configured
        print("send discovery!")
        cache[id]["discSent"] = True

        basemsg = {
            "stat_cla": "measurement",
            "state_topic": getTopic(sensor),
            "exp_aft": 300,
            "device": {
                "identifiers": [
                    type(sensor).__name__ + id
                ],
                "name": type(sensor).__name__ + " " + id,
                "manufacturer": "Seegel Systeme",
                "suggested_area": payload["room"]
            }
        }

        roomid = re.sub('\W|^(?=\d)','_', payload["room"])
        roomid = re.sub('[^0-9a-zA-Z_]', '_', payload["room"])
        roomid = re.sub('^[^a-zA-Z_]+', '', roomid)

        topic = "homeassistant/sensor/raspyrfm_" + roomid + "_T/config"
        msg = basemsg | {
                "name": "T " + payload["room"],
                "device_class": "temperature",
                "unique_id": "raspyrfm_" + roomid + "_T",
                "unit_of_meas": "°C",
                "val_tpl": "{{ value_json['T'] }}"
        }
        mqttClient.publish(topic, json.dumps(msg))

        if "RH" in payload:
            topic = "homeassistant/sensor/raspyrfm_" + roomid + "_RH/config"
            msg = basemsg | {
                    "name": "RH " + payload["room"],
                    "device_class": "humidity",
                    "unique_id": "raspyrfm_" + roomid + "_RH",
                    "unit_of_meas": "%",
                    "val_tpl": "{{ value_json['RH'] }}"
            }
            mqttClient.publish(topic, json.dumps(msg))

    lock.release()

    measurement = config["influxdb"]["measurement"] if "measurement" in config["influxdb"] else ""
    if measurement == "":
        measurement = sensor.getClass()

    if influxClient:
        try:
            wr = {
                "measurement": measurement,
                "fields": {},
                "tags": {"sensor": payload["id"] if not ("room" in payload) else payload["room"]}
            }
            val = sensor.getDbValues()
            for key in val:
               wr["fields"][key] = val[key][0]

            influxClient.write_points([wr])

        except Exception as ex:
            print("Error writing to influxdb1:", ex)

    if influxClient2:
        try:
            point = (
                Point(measurement)
                .tag("sensor", payload["id"] if not ("room" in payload) else payload["room"])
            )
            val = sensor.getDbValues()
            for key in val:
               point.field(key, val[key][0])

            influxapi.write(bucket=config["influxdb2"]["bucket"], org=config["influxdb2"]["org"], record=point)

        except Exception as ex:
            print("Error writing to influxdb2:", ex)

    if mqttClient:
        try:
            mqttClient.publish(getTopic(sensor), json.dumps(payload))
        except:
            print("Error writing to MQTT!")
