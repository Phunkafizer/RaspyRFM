#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, time, threading, math, json, os, argparse, shutil
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

script_dir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(script_dir + "/868gw.conf"):
	if os.path.exists(script_dir + "/lacrossegw.conf"):
		shutil.move(script_dir + "/lacrossegw.conf", script_dir + "/868gw.conf")
	else:
		shutil.copyfile(script_dir + "/868gw.conf.tmpl", script_dir + "/868gw.conf")
with open(script_dir + "/868gw.conf") as jfile:
    config = json.load(jfile)

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

try:
    import influxdb_client
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    influxClient2 = influxdb_client.InfluxDBClient(url=config["influxdb2"]["url"], token=config["influxdb2"]["token"], org=config["influxdb2"]["org"])
    influxapi = influxClient2.write_api(write_options=SYNCHRONOUS)
    print("InfluxDB2 client loaded")
except Exception as ex:
    influxClient2 = None
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

def getCacheSensor(id, sensorConfig = None):
    sensor = None
    if (id in cache) and ((datetime.now() - cache[id]["ts"]).total_seconds() < 180):
        sensor = cache[id]["payload"]
        if sensorConfig is not None:
            if ('tMax' in sensorConfig) and (sensor["T"] > sensorConfig["tMax"]):
                sensor["tStatus"] = "high"

            if ('tMin' in sensorConfig) and (sensor["T"] < sensorConfig["tMin"]):
                sensor["tStatus"] = "low"

            if ('tStatus' not in sensor) and ('tMax' in sensorConfig or 'tMin' in sensorConfig):
                sensor["tStatus"] = "ok"

            if ('isOutside' in sensorConfig):
                sensor["isOutside"] = sensorConfig['isOutside']

            if ('RH' in sensor):
                outSensor = getCacheSensor(sensorConfig["idOutside"]) if 'idOutside' in sensorConfig else None
                if (outSensor is not None) and ('AH' in outSensor):
                    sensor["AHratio"] = round((outSensor["AH"] / sensor["AH"] - 1) * 100)
                    sensor["RHvent"] = round(outSensor["VP"] / sensor["SVP"] * 100)

                if ('rhMax' in sensorConfig) and (sensor["RH"] > sensorConfig["rhMax"]):
                    #too wet!
                    sensor["rhStatus"] = "high"
                    if "AHratio" in sensor:
                        if sensor["AHratio"] <= -10:
                            sensor["window"] = "open"
                        elif sensor["AHratio"] >= 10:
                            sensor["window"] = "close"

                if ('rhMin' in sensorConfig) and (sensor["RH"] < sensorConfig["rhMin"]):
                    #too dry
                    sensor["rhStatus"] = "low"
                    if "AHratio" in sensor:
                        if sensor["AHratio"] >= 10:
                            sensor["window"] = "open"
                        elif sensor["AHratio"] <= -10:
                            sensor["window"] = "close"

                if 'rhStatus' not in sensor and ('rhMin' in sensorConfig or 'rhMax' in sensorConfig):
                    sensor["rhStatus"] = "ok"

    return sensor

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
            sensor = getCacheSensor(id, csens)
            if sensor is not None:
                idlist.append(id)
            else:
                sensor = {}
                sensor["room"] = csens["name"]
            sensor["id"] = id
            resp["sensors"].append(sensor)

        for id in cache:
            if id in idlist:
                continue

            sensor = getCacheSensor(id)
            if sensor is not None:
                resp["sensors"].append(sensor)

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
            print("config save!")
            content_len = int(self.headers.get('content-length'))
            print("len:", content_len)
            s = self.rfile.read(content_len)
            print("read string", s)
            conf = json.loads(s)
            print("config now: ", conf)
            global config
            config = conf
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

cache = {}
p = config["webport"] if "webport" in config else 8080
server = Server(('0.0.0.0', p), MyHttpRequestHandler)
server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True
server_thread.start()

p = config["apiport"] if "apiport" in config else 1991
apisrv = apiserver.ApiServer(p)

while 1:
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
    #print("Current config", config)
    for csens in config["sensors"]:
        if id == csens["id"]:
            payload["room"] = csens["name"]
            if 'Tsurf' in csens and 'T' in sensorValues and 'RH' in sensorValues:
                aw = round(climatools.calcAw(payload['T'], payload['RH'], csens['Tsurf']))
                if aw > 100:
                    aw = 100
                payload["aw"] = aw
                awWarn = csens["awWarn"] if 'awWarn' in csens else 80
                payload["awStatus"] = 'high' if aw >= awWarn else 'ok'
            break

    apipayl = {
        "decode": [{
            "protocol": sensor.getType(),
            "params": payload,
            "class": sensor.getClass()
        }]
    }
    apisrv.send(apipayl)

    if not id in cache:
        cache[id] = {}
    cache[id]["payload"] = payload
    cache[id]["ts"] = datetime.now()
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
            if "mqtt" in config and "basetopic" in config["mqtt"]:
                topic = config["mqtt"]["basetopic"]
            else:
                topic = "home"
            topic += "/" + sensor.getClass() + "/" + payload['id']
            mqttClient.publish(topic, json.dumps(payload))
        except:
            print("Error writing to MQTT!")
