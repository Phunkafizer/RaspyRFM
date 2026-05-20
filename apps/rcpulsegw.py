#!/usr/bin/env python3

from re import split
from raspyrfm import *
import rcprotocols
import json
from argparse import ArgumentParser
import apiserver, time, os, shutil
import socket
import threading
import atexit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MQTT_BASE_TOPIC = "home/rcpulse"

try:
    import paho.mqtt.client as mqtt
    mqttClient = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except:
    mqttClient = None
    print("mqtt init error")

parser = ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
args = parser.parse_args()

script_dir = os.path.dirname(os.path.realpath(__file__))
if not os.path.exists(script_dir + "/rcpulsegw.conf"):
    shutil.copyfile(script_dir + "/rcpulsegw.conf.tmpl", script_dir + "/rcpulsegw.conf")
with open(script_dir + "/rcpulsegw.conf") as jfile:
    config = json.load(jfile)


def _detect_local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except:
        return "127.0.0.1"


def _start_mdns_http(http_port):
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except Exception as ex:
        print("mDNS disabled (zeroconf not available):", ex)
        return (None, None)

    hostname = config["mdns_name"] if "mdns_name" in config else "rfm-gateway"
    ip = config["mdns_ip"] if "mdns_ip" in config else _detect_local_ip()

    zc = Zeroconf()
    try:
        info = ServiceInfo(
            "_http._tcp.local.",
            f"{hostname}._http._tcp.local.",
            addresses=[socket.inet_aton(ip)],
            port=http_port,
            properties={
                b"path": b"/",
                b"rf_api": b"1",
            },
            server=f"{hostname}.local.",
        )
        zc.register_service(info)
        print("mDNS registered:", f"{hostname}.local", "port", http_port, "ip", ip)
        return (zc, info)
    except Exception as ex:
        print("mDNS registration failed:", ex)
        try:
            zc.close()
        except:
            pass
        return (None, None)


class RfApiHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Keep gateway output concise.
        return

    def do_GET(self):
        if self.path == "/api/rf/capabilities":
            payload = {
                "device_name": "RaspyRFM 433 MHz RC Pulse Gateway",
                "supported_frequency_ranges": [[430_000_000, 440_000_000]],
                "supported_modulations": ["ook"],
            }
            self._send_json(200, payload)
            return

        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path != "/api/rf/transmit":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length) if length > 0 else b""
        try:
            req = json.loads(data.decode("utf-8")) if data else {}
            rctrx.sendRaw(req["timings_us"], req["repeat_count"])
            self._send_json(200, {"ok": True, "message": "Sent successfully."})

        except:
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return

def _start_http_api_server(port):
    srv = ThreadingHTTPServer(("", port), RfApiHandler)
    t = threading.Thread(target=srv.serve_forever)
    t.daemon = True
    t.start()
    print("RF HTTP API listening on port", port)
    return srv


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
    try:
        rctrx.send(data["protocol"], data["params"])
    except:
        pass


p = config["apiport"] if "apiport" in config else 1989
apisrv = apiserver.ApiServer(p, apicb)

http_api_port = config["http_api_port"] if "http_api_port" in config else 8099
http_api_srv = _start_http_api_server(http_api_port)
mdns = _start_mdns_http(http_api_port)


def _cleanup():
    try:
        http_api_srv.shutdown()
    except:
        pass

    zc = mdns[0]
    info = mdns[1]
    if zc and info:
        try:
            zc.unregister_service(info)
        except:
            pass
        try:
            zc.close()
        except:
            pass


atexit.register(_cleanup)


def on_connect(client, userdata, flags, rc, props):
    print("Connected MQTT with result code " + str(rc))
    if rc == 0:
        client.subscribe(MQTT_BASE_TOPIC + "/#")
    # client.connected_flag = rc == 0


def on_disconnect(client, userdata, rc):
    print("MQTT disconnected")
    # client.connected_flag = False


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
    mqttClient.connected_flag = False
    mqttClient.loop_start()
    mqttClient.on_connect = on_connect
    mqttClient.on_disconnect = on_disconnect
    mqttClient.on_message = on_message
    mqttClient.username_pw_set(
        config["mqtt"]["user"] if ("mqtt" in config) and ("user" in config["mqtt"]) else "",
        config["mqtt"]["pass"] if ("mqtt" in config) and ("pass" in config["mqtt"]) else None,
    )
    server = config["mqtt"]["server"] if ("mqtt" in config) and ("server" in config["mqtt"]) else "127.0.0.1"
    port = config["mqtt"]["port"] if ("mqtt" in config) and ("port" in config["mqtt"]) else 1883
    try:
        mqttClient.connect(server, port, 30)
    except:
        pass

while True:
    time.sleep(1)
