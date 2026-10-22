#!/usr/bin/env python3

from re import split
from raspyrfm import *
import rcprotocols
import json
from argparse import ArgumentParser
import apiserver, time, os, shutil
import traceback
import socket
import threading
import atexit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MQTT_BASE_TOPIC = "home/rcpulse"

# Load HTML UI from external file
script_dir = os.path.dirname(os.path.realpath(__file__))
with open(os.path.join(script_dir, "rc433.html"), "r") as f:
    WEB_UI_HTML = f.read()


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


def _build_ook_payload(timings_us, repeat_count, timebase_us=50):
    pulse_counts = [round(abs(int(duration)) / timebase_us) for duration in timings_us]
    numbits = 0
    ookdata = bytearray()
    bbuf = 0
    bval = 0

    def add_pulses(pulses):
        nonlocal numbits, ookdata, bbuf, bval
        for pulse in pulses:
            bval ^= 1
            for _ in range(pulse):
                bbuf <<= 1
                bbuf |= bval
                numbits += 1
                if numbits == 8:
                    ookdata.append(bbuf)
                    bbuf = 0
                    numbits = 0

    add_pulses(pulse_counts)
    if numbits > 0:
        bval ^= 1
        add_pulses([8 - numbits])

    return ookdata * int(repeat_count), timebase_us


def _start_mdns_http(http_port):
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except Exception as ex:
        print("mDNS disabled (zeroconf not available):", ex)
        return (None, None)

    hostname = config["mdns_name"] if "mdns_name" in config else "raspyrfm"
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
                b"model": b"rfm-gateway",
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


def _send_protocol_request(req):
    proto = str(req.get("protocol", "")).strip()
    if not proto:
        raise ValueError("protocol is required")
    rctrx.send(proto, req)


def _send_discovery_request(req):
    if not mqttClient:
        raise RuntimeError("MQTT client is not available.")
    if not mqttClient.is_connected():
        raise RuntimeError("MQTT client is not connected.")
    proto = str(req.get("protocol", "")).strip()
    if not proto:
        raise ValueError("protocol is required")
    mqtt_cfg = config["mqtt"] if "mqtt" in config else {}
    discovery_prefix = mqtt_cfg["ha_prefix"] if "ha_prefix" in mqtt_cfg else "homeassistant"
    device_id = mqtt_cfg["discovery_device_id"] if "discovery_device_id" in mqtt_cfg else "raspyrfm_rcpulse"
    device_name = config["device_name"] if "device_name" in config else "RaspyRFM 433 MHz RC Pulse Gateway"
    clear = bool(req.get("clear", False))
    topic, payload = rcprotocols.get_discovery_config(proto, req, MQTT_BASE_TOPIC, discovery_prefix, device_id, device_name, clear)
    payload_data = payload if isinstance(payload, str) else json.dumps(payload)
    result = mqttClient.publish(topic, payload_data, 0, True)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"MQTT publish failed: {result.rc}")
    return topic



class RfApiHandler(BaseHTTPRequestHandler):
    def _send_response(self, status, content_type, body_bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_json(self, status, payload):
        self._send_response(status, "application/json", json.dumps(payload).encode("utf-8"))

    def _send_html(self, status, html):
        self._send_response(status, "text/html; charset=utf-8", html.encode("utf-8"))

    def _read_json_request(self):
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length) if length > 0 else b""
        try:
            return json.loads(data.decode("utf-8")) if data else {}
        except Exception as ex:
            raise ValueError(f"invalid_json: {ex}")

    def log_message(self, format, *args):
        return

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._send_html(200, WEB_UI_HTML)
            return
        if path == "/api/rf/capabilities":
            payload = {
                "device_name": "RaspyRFM 433 MHz RC Pulse Gateway",
                "supported_frequency_ranges": [[430_000_000, 440_000_000]],
                "supported_modulations": ["ook"],
            }
            self._send_json(200, payload)
            return
        self._send_json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path in ("/send", "/send/"):
            try:
                req = self._read_json_request()
                print("HTTP protocol transmit:", req, flush=True)
                _send_protocol_request(req)
                self._send_json(200, {"ok": True, "message": "Sent successfully."})
            except KeyError as ex:
                self._send_json(400, {"ok": False, "error": "invalid_request", "detail": f"missing field: {ex.args[0]}"})
            except ValueError as ex:
                self._send_json(400, {"ok": False, "error": "invalid_request", "detail": str(ex)})
            except Exception as ex:
                print("Protocol transmit failed:", repr(ex))
                traceback.print_exc()
                self._send_json(500, {"ok": False, "error": "transmit_failed", "detail": str(ex)})
            return
        if path in ("/senddisc", "/senddisc/"):
            try:
                req = self._read_json_request()
                print("HTTP HA discovery:", req, flush=True)
                topic = _send_discovery_request(req)
                message = "Discovery cleared." if bool(req.get("clear", False)) else "Discovery sent successfully."
                self._send_json(200, {"ok": True, "message": message, "topic": topic})
            except KeyError as ex:
                self._send_json(400, {"ok": False, "error": "invalid_request", "detail": f"missing field: {ex.args[0]}"})
            except ValueError as ex:
                self._send_json(400, {"ok": False, "error": "invalid_request", "detail": str(ex)})
            except RuntimeError as ex:
                self._send_json(503, {"ok": False, "error": "mqtt_unavailable", "detail": str(ex)})
            except Exception as ex:
                print("HA discovery failed:", repr(ex), flush=True)
                traceback.print_exc()
                self._send_json(500, {"ok": False, "error": "discovery_failed", "detail": str(ex)})
            return
        if path != "/api/rf/transmit":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return
        try:
            req = self._read_json_request()
            timings = req["timings_us"]
            repeats = req["repeat_count"]
        except ValueError as ex:
            self._send_json(400, {"ok": False, "error": "invalid_json", "detail": str(ex)})
            return
        except KeyError as ex:
            self._send_json(400, {"ok": False, "error": "invalid_request", "detail": f"missing field: {ex.args[0]}"})
            return
        try:
            print("HTTP RF transmit:", {"timings_us": timings, "repeat_count": repeats}, flush=True)
            ook, timebase_us = _build_ook_payload(timings, repeats)
            rctrx._RcTransceiver__rfmtrx.send(ook, timebase_us)
            self._send_json(200, {"ok": True, "message": "Sent successfully."})
        except Exception as ex:
            print("RF transmit failed:", repr(ex))
            traceback.print_exc()
            self._send_json(500, {"ok": False, "error": "transmit_failed", "detail": str(ex)})


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


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print("MQTT disconnected", reason_code)


def on_message(client, userdata, msg):
    try:
        tl = msg.topic.split("/")
        tl = tl[len(MQTT_BASE_TOPIC.split("/")):]
        if (len(tl) < 2) or (tl[-1] != "set"):
            return
        proto = tl[0]
        payload = msg.payload.decode()
        proto_handler = rcprotocols.get_protocol(proto)
        params = proto_handler.getMqttParamsFromMessage(tl[1:-1], payload) if proto_handler else (tl[1:-1] + [payload])
        print("TX from MQTT: " + proto + " " + str(params))
        rctrx.send(proto, params)
    except Exception as ex:
        print("MQTT message handling failed:", repr(ex))
        traceback.print_exc()


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
