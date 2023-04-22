#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, time, threading, math, json, os, argparse
from raspyrfm import *
import sensors
from datetime import datetime
import apiserver

try:
    #python2.7
    import SocketServer as socketserver
    from urlparse import urlparse, parse_qs
    from SimpleHTTPServer import SimpleHTTPRequestHandler as Handler
except ImportError:
    #python3
    import socketserver
    from http.server import SimpleHTTPRequestHandler as Handler
    from urllib.parse import urlparse, parse_qs

lock = threading.Lock()
event = threading.Event()
event.set()
rfmlock = threading.Lock()

script_dir = os.path.dirname(os.path.realpath(__file__))
with open(script_dir + "/lacrossegw.conf") as jfile:
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

    createDb = True
    for db in influxClient.get_list_database():
        if db["name"] == config["influxdb"]["database"]:
            createDb = False
            break
    if createDb:
        influxClient.create_database(config["influxdb"]["database"])
        influxClient.switch_database(config["influxdb"]["database"])
        influxClient.alter_retention_policy("autogen", duration="2h", replication=1, shard_duration="1h")
        influxClient.create_retention_policy("one_week", duration="1w", replication=1, shard_duration='24h')
        influxClient.create_retention_policy("one_year", database=config["influxdb"]["database"], duration="365d", replication=1, shard_duration='1w')
        influxClient.create_continuous_query("three_min", 'SELECT mean(T) as "T", mean(RH) as "RH", mean(AH) as "AH", mean(DEW) as "DEW" INTO "one_week"."lacrosse" from "lacrosse" GROUP BY time(3m),*')
        influxClient.create_continuous_query("three_hour", 'SELECT mean(T) as "T", mean(RH) as "RH", mean(AH) as "AH", mean(DEW) as "DEW" INTO "one_week"."lacrosse" from "lacrosse" GROUP BY time(3h),*')
    else:
        influxClient.switch_database(config["influxdb"]["database"])

except Exception as ex:
    influxClient = None
    print("influx init error: " + ex.__class__.__name__ + " " + (''.join(ex.args)))

try:
    import paho.mqtt.client as mqtt
    mqttClient = mqtt.Client()
    mqttClient.connect("localhost", 1883, 60)
    mqttClient.loop_start()
except:
    mqttClient = None
    print("mqtt init error")

rfm.set_params(
    Freq = 868.300, # MHz center frequency
    Datarate = 9.579, # kbit/s baudrate
    ModulationType = rfm69.FSK, # modulation
    SyncPattern = [0x2d, 0xd4], # syncword
    Bandwidth = 200, # kHz
    AfcBandwidth = 200, # kHz
    #AfcFei = 0x0C, # AFC auto clear, AFC auto on
    RssiThresh = -110, # dBm RSSI threshold
)

class BaudChanger(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        baudrates = [9.579, 17.241]
        i = 0
        while True:
            time.sleep(15)
            rfm.receive_stop()
            i += 1
            if i == len(baudrates):
                i = 0
            bd = baudrates[i]

            print("Switch baudrate to " + str(bd) + " kbit/s")
            rfmlock.acquire()
            rfm.set_params(Datarate = bd)
            rfmlock.release()

baudChanger = BaudChanger()

def writeInflux(payload):
    if not influxClient:
        return
    T = payload["T"]
    wr = {
        "measurement": "lacrosse",
        "fields": {
            "T": T
        },
        "tags": {"sensor": payload["id"] if not ("room" in payload) else payload["room"]}
    }

    if ("RH" in payload):
        wr["fields"]["RH"] = payload['RH']
        wr["fields"]["DEW"] = payload["DEW"]
        wr["fields"]["AH"] = payload["AH"]

    influxClient.write_points([wr])

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

            if ('RH' in sensor):
                outSensor = getCacheSensor(sensorConfig["idOutside"]) if 'idOutside' in sensorConfig else None
                if (outSensor is not None) and ('AH' in outSensor):
                    sensor["AHratio"] = round((outSensor["AH"] / sensor["AH"] - 1) * 100)
                    sensor["RHvent"] = round(outSensor["DD"] / sensor["SDD"] * 100)

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

class MyHttpRequestHandler(Handler):
    def getjson(self):
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
            self.getjson()

        elif p == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

            with open(script_dir + '/index.html', 'rb') as file:
                self.wfile.write(file.read())

        elif p == '/history' and influxClient and name:
            resp = influxClient.query(
                "SELECT mean(T), mean(RH) FROM one_week.lacrosse WHERE (sensor = $name) AND time >= now() - 4h GROUP BY time(3m) fill(none)",
                bind_params={'name': name}
                )
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp.raw['series'][0]['values']).encode())
        else:
            return self.send_error(404, self.responses.get(404)[0])


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

print("Waiting for sensors...")

while 1:
    rfmlock.acquire()
    rxObj = rfm.receive(7)
    rfmlock.release()

    try:
        sensorObj = sensors.rawsensor.CreateSensor(rxObj)
        sensorData = sensorObj.GetData()
        payload = {}
        id = sensorData["ID"]
        payload["id"] = id
        T = sensorData["T"][0]
        payload["T"] = T
    except:
        continue

    payload["rssi"] = rxObj[1]
    payload["afc"] = rxObj[2]
    payload["batlo"] = sensorData['batlo']
    payload["init"] = sensorData["init"]
    lock.acquire()
    for csens in config["sensors"]:
        if id == csens["id"]:
            payload["room"] = csens["name"]
            break

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
        payload["SDD"] = SDD
        payload["DD"] = DD

        DD = RH / 80.0 * SDD
        v = math.log10(DD/6.1078)
        payload["DEW80"] = round(b*v/(a-v), 1)

        DD = RH / 60.0 * SDD
        v = math.log10(DD/6.1078)
        payload["DEW60"] = round(b*v/(a-v), 1)

    apipayl = {
        "decode": [{
            "protocol": "lacrosse",
            "params": payload,
            "class": "weather"
        }]
    }
    apisrv.send(apipayl)

    if not id in cache:
        cache[id] = {}
        cache[id]["count"] = 1
        cache[id]["payload"] = payload
        cache[id]["payload"]["tMin"] = T
        cache[id]["payload"]["tMax"] = T
    else:
        payload["tMin"] = cache[id]["payload"]["tMin"]
        payload["tMax"] = cache[id]["payload"]["tMax"]
        if payload["tMin"] > T:
            payload["tMin"] = T
        if payload["tMax"] < T:
            payload["tMax"] = T

        cache[id]["payload"] = payload

    cache[id]["ts"] = datetime.now()
    cache[id]["count"] += 1

    line = "|id: {:2}  ".format(id)
    line += '{:12}|'.format(payload["room"][:12] if ("room" in payload) else "---")
    line += 'T: {:5.1f} C|'.format(payload["T"])
    if "RH" in payload:
        line += 'RH: {:2} %|'.format(payload["RH"])
    else:
        line += 'RH: -- %|'
    line += "battery: " + ("LOW" if payload["batlo"] else "OK ") + "|"
    line += "init: " + ("1" if payload["init"] else "0") + "|"
    line += "RSSI: {:6.1f} dBm|".format(rxObj[1])
    line += "FEI: {:5.1f} kHz|".format(rxObj[3] * rfm69.FSTEP / 1000)
    print(line)
    lock.release()

    try:
        if influxClient:
            writeInflux(payload)
    except:
        print("Error writing to influx")

    try:
        if mqttClient:
            mqttClient.publish('home/lacrosse/'+ payload['id'], json.dumps(payload))
    except:
        print("Error writing to MQTT!")
