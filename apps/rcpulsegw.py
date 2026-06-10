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

WEB_UI_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>RaspyRFM Send Signal</title>
    <style>
        :root {
            --bg: #10161d;
            --panel: #17212b;
            --line: rgba(148, 163, 184, 0.18);
            --text: #e5edf5;
            --muted: #9db0c2;
            --accent: #4fb3ff;
            --accent-2: #2b89cf;
            --danger: #d95c5c;
            --ok: #3dbb7b;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            font-family: Arial, sans-serif;
            color: var(--text);
            background:
                radial-gradient(720px 320px at 0% 0%, rgba(79, 179, 255, 0.16), transparent 60%),
                radial-gradient(720px 320px at 100% 0%, rgba(61, 187, 123, 0.12), transparent 60%),
                linear-gradient(180deg, #111923, var(--bg));
        }
        .page {
            max-width: 920px;
            margin: 0 auto;
            padding: 24px 16px 40px;
        }
        .hero { margin-bottom: 18px; }
        .eyebrow {
            color: var(--accent);
            font-size: 12px;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        h1 { margin: 0; font-size: 30px; line-height: 1.1; }
        .sub { margin-top: 8px; color: var(--muted); max-width: 52rem; }
        .card {
            background: linear-gradient(180deg, rgba(29, 42, 54, 0.96), rgba(23, 33, 43, 0.96));
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.25);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 14px;
        }
        .field { grid-column: span 12; }
        .field.half { grid-column: span 6; }
        .field.third { grid-column: span 4; }
        label {
            display: block;
            margin-bottom: 7px;
            color: var(--muted);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        input, select, button {
            width: 100%;
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 12px;
            background: rgba(11, 17, 23, 0.55);
            color: var(--text);
            padding: 12px 14px;
            font-size: 15px;
        }
        .proto-panel { display: none; margin-top: 16px; }
        .proto-panel.active { display: block; }
        .actions {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 18px;
        }
        .actions button {
            width: auto;
            min-width: 140px;
            cursor: pointer;
            font-weight: 700;
        }
        .primary { background: linear-gradient(180deg, var(--accent), var(--accent-2)); color: #08121b; border: none; }
        .secondary { background: rgba(79, 179, 255, 0.12); }
        .danger { background: rgba(217, 92, 92, 0.14); }
        .hint {
            margin-top: 16px;
            padding: 12px 14px;
            border-radius: 12px;
            background: rgba(11, 17, 23, 0.5);
            border: 1px solid var(--line);
            color: var(--muted);
            line-height: 1.45;
        }
        .hint.error { color: #ffd5d5; border-color: rgba(217, 92, 92, 0.4); background: rgba(217, 92, 92, 0.12); }
        .hint.ok { color: #d5ffe8; border-color: rgba(61, 187, 123, 0.4); background: rgba(61, 187, 123, 0.12); }
        @media (max-width: 720px) {
            .field.half, .field.third { grid-column: span 12; }
            h1 { font-size: 26px; }
            .actions button { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="page">
        <div class="hero">
            <div class="eyebrow">RaspyRFM 433 MHz Gateway</div>
            <h1>Send signal</h1>
        </div>
        <div class="card">
            <div class="grid">
                <div class="field">
                    <label for="protocol">Protocol</label>
                    <select id="protocol">
                        <option value="ittristate">Intertechno tristate</option>
                        <option value="2">Brennenstuhl</option>
                        <option value="intertechno">Intertechno 32</option>
                        <option value="pilota">Pilota casa</option>
                        <option value="emylo">Emylo</option>
                        <option value="EV1527">EV1527</option>
                    </select>
                </div>
            </div>
            <div id="panel-ittristate" class="proto-panel active">
                <div class="grid">
                    <div class="field third">
                        <label for="ittristate-house">House (A-P)</label>
                        <select id="ittristate-house"></select>
                    </div>
                    <div class="field third">
                        <label for="ittristate-group">Group (1-4, 0 = all)</label>
                        <select id="ittristate-group"><option value="0">all</option><option value="1" selected>1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select>
                    </div>
                    <div class="field third">
                        <label for="ittristate-channel">Channel (1-4, 0 = all)</label>
                        <select id="ittristate-channel"><option value="0">all</option><option value="1" selected>1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select>
                    </div>
                </div>
                <div class="actions"><button class="primary" data-command="ON">ON</button><button class="secondary" data-command="OFF">OFF</button></div>
            </div>
            <div id="panel-2" class="proto-panel"><div class="hint error">Brennenstuhl is shown for compatibility with the reference UI, but it is not implemented by this gateway yet.</div></div>
            <div id="panel-intertechno" class="proto-panel">
                <div class="grid">
                    <div class="field half"><label for="intertechno-id">ID</label><input id="intertechno-id" type="number" min="0" placeholder="e.g. 123456"></div>
                    <div class="field half"><label for="intertechno-channel">Channel (1-16)</label><select id="intertechno-channel"></select></div>
                </div>
                <div class="actions"><button class="primary" data-command="ON">ON</button><button class="secondary" data-command="OFF">OFF</button></div>
            </div>
            <div id="panel-pilota" class="proto-panel">
                <div class="grid">
                    <div class="field half"><label for="pilota-id">ID</label><input id="pilota-id" type="number" min="0" placeholder="e.g. 123456"></div>
                    <div class="field third"><label for="pilota-group">Group (1-4)</label><select id="pilota-group"></select></div>
                    <div class="field third"><label for="pilota-channel">Channel (1-3)</label><select id="pilota-channel"></select></div>
                </div>
                <div class="actions"><button class="primary" data-command="ON">ON</button><button class="secondary" data-command="OFF">OFF</button></div>
            </div>
            <div id="panel-emylo" class="proto-panel">
                <div class="grid">
                    <div class="field half"><label for="emylo-id">ID (0-1048575)</label><input id="emylo-id" type="number" min="0" max="1048575" placeholder="e.g. 123456"></div>
                    <div class="field half"><label for="emylo-discovery-key">Discovery key</label><select id="emylo-discovery-key"><option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option></select></div>
                </div>
                <div class="actions"><button class="primary" data-command="A">A</button><button class="secondary" data-command="B">B</button><button class="secondary" data-command="C">C</button><button class="danger" data-command="D">D</button></div>
            </div>
            <div id="panel-EV1527" class="proto-panel">
                <div class="grid">
                    <div class="field half"><label for="ev1527-id">ID (0-1048575)</label><input id="ev1527-id" type="number" min="0" max="1048575" placeholder="e.g. 123456"></div>
                    <div class="field half"><label for="ev1527-data">Data (0-15)</label><input id="ev1527-data" type="number" min="0" max="15" placeholder="e.g. 8"></div>
                </div>
                <div class="actions"><button id="ev1527-send" class="primary">Send</button></div>
            </div>
            <div class="actions"><button id="discovery-send" class="secondary">Send HA discovery</button><button id="discovery-clear" class="danger">Clear HA discovery</button></div>
            <div id="result" class="hint">Ready.</div>
        </div>
    </div>
    <script>
        function fillSelect(id, from, to, selected) {
            const select = document.getElementById(id);
            for (let value = from; value <= to; value += 1) {
                const option = document.createElement('option');
                option.value = String(value);
                option.textContent = String(value);
                if (value === selected) option.selected = true;
                select.appendChild(option);
            }
        }
        function showPanel(protocol) {
            for (const panel of document.querySelectorAll('.proto-panel')) panel.classList.toggle('active', panel.id === 'panel-' + protocol);
            setResult('Ready.', false, false);
        }
        function setResult(message, isError, isOk) {
            const node = document.getElementById('result');
            node.textContent = message;
            node.classList.toggle('error', Boolean(isError));
            node.classList.toggle('ok', Boolean(isOk));
        }
        function requireInt(id, name) {
            const raw = document.getElementById(id).value.trim();
            if (raw === '') throw new Error(name + ' is required.');
            const value = Number(raw);
            if (!Number.isInteger(value)) throw new Error(name + ' must be an integer.');
            return value;
        }
        function buildPayload(command) {
            const protocol = document.getElementById('protocol').value;
            switch (protocol) {
                case 'ittristate': {
                    const payload = { protocol, house: document.getElementById('ittristate-house').value, command };
                    const group = Number(document.getElementById('ittristate-group').value);
                    const channel = Number(document.getElementById('ittristate-channel').value);
                    payload.group = group;
                    payload.channel = channel;
                    return payload;
                }
                case '2':
                    throw new Error('Brennenstuhl is not supported by this gateway yet.');
                case 'intertechno':
                    return { protocol, id: requireInt('intertechno-id', 'ID'), channel: Number(document.getElementById('intertechno-channel').value), command };
                case 'pilota':
                    return { protocol, id: requireInt('pilota-id', 'ID'), group: Number(document.getElementById('pilota-group').value), channel: Number(document.getElementById('pilota-channel').value), command };
                case 'emylo':
                    return { protocol, id: requireInt('emylo-id', 'ID'), key: command || document.getElementById('emylo-discovery-key').value };
                case 'EV1527':
                    return { protocol, id: requireInt('ev1527-id', 'ID'), data: requireInt('ev1527-data', 'Data') };
                default:
                    throw new Error('Unsupported protocol.');
            }
        }
        async function postPayload(payload) {
            setResult('Sending...', false, false);
            const response = await fetch('/send/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            let body = {};
            try { body = await response.json(); } catch (_) { body = {}; }
            if (!response.ok || !body.ok) throw new Error(body.detail || body.error || ('HTTP ' + response.status));
            setResult(body.message || 'Sent successfully.', false, true);
        }
        async function postDiscovery(payload, clear) {
            const discoveryPayload = { ...payload };
            if (clear) discoveryPayload.clear = true;
            setResult(clear ? 'Clearing HA discovery...' : 'Sending HA discovery...', false, false);
            const response = await fetch('/senddisc', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(discoveryPayload) });
            let body = {};
            try { body = await response.json(); } catch (_) { body = {}; }
            if (!response.ok || !body.ok) throw new Error(body.detail || body.error || ('HTTP ' + response.status));
            setResult(body.message || (clear ? 'Discovery cleared.' : 'Discovery sent successfully.'), false, true);
        }
        fillSelect('intertechno-channel', 1, 16, 1);
        fillSelect('pilota-group', 1, 4, 1);
        fillSelect('pilota-channel', 1, 3, 1);
        for (const house of 'ABCDEFGHIJKLMNOP') {
            const option = document.createElement('option');
            option.value = house;
            option.textContent = house;
            document.getElementById('ittristate-house').appendChild(option);
        }
        document.getElementById('protocol').addEventListener('change', (event) => showPanel(event.target.value));
        showPanel(document.getElementById('protocol').value);
        for (const button of document.querySelectorAll('[data-command]')) {
            button.addEventListener('click', async () => {
                try { await postPayload(buildPayload(button.dataset.command)); }
                catch (error) { setResult(error.message, true, false); }
            });
        }
        document.getElementById('ev1527-send').addEventListener('click', async () => {
            try { await postPayload(buildPayload()); }
            catch (error) { setResult(error.message, true, false); }
        });
        document.getElementById('discovery-send').addEventListener('click', async () => {
            try { await postDiscovery(buildPayload(), false); }
            catch (error) { setResult(error.message, true, false); }
        });
        document.getElementById('discovery-clear').addEventListener('click', async () => {
            try { await postDiscovery(buildPayload(), true); }
            catch (error) { setResult(error.message, true, false); }
        });
    </script>
</body>
</html>
"""

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


def _get_int_value(req, field_name, minimum=None, maximum=None):
    if field_name not in req:
        raise KeyError(field_name)
    value = int(req[field_name])
    if (minimum is not None) and (value < minimum):
        raise ValueError(f"{field_name} must be >= {minimum}")
    if (maximum is not None) and (value > maximum):
        raise ValueError(f"{field_name} must be <= {maximum}")
    return value


def _build_protocol_payload(req, require_command=True):
    proto = str(req.get("protocol", "")).strip()
    if proto == "ittristate":
        house = str(req.get("house", "")).strip().upper()
        if house not in "ABCDEFGHIJKLMNOP":
            raise ValueError("house must be between A and P")
        command = str(req.get("command", "")).strip().upper()
        params = [house]
        if "group" in req:
            params.append(str(int(req["group"])))
        if "channel" in req:
            params.append(str(int(req["channel"])))
        if command:
            if command not in ("ON", "OFF"):
                raise ValueError("command must be ON or OFF")
            params.append(command)
        elif require_command:
            raise ValueError("command must be ON or OFF")
        return proto, params
    if proto == "2":
        raise ValueError("protocol 2 (Brennenstuhl) is not supported")
    if proto == "intertechno":
        device_id = _get_int_value(req, "id", 0)
        channel = _get_int_value(req, "channel", 1, 16)
        command = str(req.get("command", "")).strip().upper()
        params = [str(device_id), str(channel)]
        if command:
            if command not in ("ON", "OFF"):
                raise ValueError("command must be ON or OFF")
            params.append(command)
        elif require_command:
            raise ValueError("command must be ON or OFF")
        return proto, params
    if proto == "pilota":
        device_id = _get_int_value(req, "id", 0)
        group = _get_int_value(req, "group", 1, 4)
        channel = _get_int_value(req, "channel", 1, 3)
        command = str(req.get("command", "")).strip().upper()
        params = [str(device_id), str(group), str(channel)]
        if command:
            if command not in ("ON", "OFF"):
                raise ValueError("command must be ON or OFF")
            params.append(command)
        elif require_command:
            raise ValueError("command must be ON or OFF")
        return proto, params
    if proto == "emylo":
        device_id = _get_int_value(req, "id", 0, 1048575)
        key = str(req.get("key", "")).strip().upper()
        if key not in ("A", "B", "C", "D"):
            raise ValueError("key must be A, B, C, or D")
        return proto, [str(device_id), key]
    if proto == "EV1527":
        device_id = _get_int_value(req, "id", 0, 1048575)
        data = _get_int_value(req, "data", 0, 15)
        return proto, [str(device_id), str(data)]
    raise ValueError(f"unsupported protocol: {proto}")


def _send_protocol_request(req):
    proto, params = _build_protocol_payload(req, require_command=True)
    rctrx.send(proto, params)


def _send_discovery_request(req):
    if not mqttClient:
        raise RuntimeError("MQTT client is not available.")
    if not mqttClient.is_connected():
        raise RuntimeError("MQTT client is not connected.")
    proto, params = _build_protocol_payload(req, require_command=False)
    mqtt_cfg = config["mqtt"] if "mqtt" in config else {}
    discovery_prefix = mqtt_cfg["ha_prefix"] if "ha_prefix" in mqtt_cfg else "homeassistant"
    device_id = mqtt_cfg["discovery_device_id"] if "discovery_device_id" in mqtt_cfg else "raspyrfm_rcpulse"
    device_name = config["device_name"] if "device_name" in config else "RaspyRFM 433 MHz RC Pulse Gateway"
    clear = bool(req.get("clear", False))
    topic, payload = rcprotocols.get_discovery_config(proto, params, MQTT_BASE_TOPIC, discovery_prefix, device_id, device_name, clear)
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
