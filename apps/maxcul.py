#!/usr/bin/env python3
# culfw (CUL) emulation for MAX! (Moritz) on a RaspyRFM RFM69.
#
# Acts as a network CUL (CUN) on TCP port 2323 for the Home Assistant
# integration "MAX! via CUL" (thnow/MAX-via-Cul).
# Devices must be paired in Home Assistant; overheard traffic is not discovery.
# Received RF frames are forwarded to all connected clients as
# "Z<hex>" lines (RSSI only after X21). Zs sends with a wake-up preamble,
# Zf sends without it; Za/Zw configure the culfw automatic ACK addresses.

from raspyrfm import *
import socket
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
import math

TCP_PORT = 2323
VERSION_STRING = "V 1.67 CUL868 (RaspyRFM maxcul gateway)"
DATARATE = 9.992
# Enforce the culfw style 1% duty cycle send budget (900 s credit).
# Set to False to disable the limit, e.g. for testing.
CREDIT_LIMIT_ENABLED = False
# Announce the TCP interface via mDNS (_maxcul._tcp) so the Home Assistant
# integration can discover the gateway on the network. Set to False to disable.
MDNS_ENABLED = True
MDNS_SERVICE_TYPE = "_maxcul._tcp.local."

@dataclass
class Transmission:
	frame: list
	long_preamble: bool
	done: threading.Event = field(default_factory=threading.Event)
	sent: bool = False

def crc16(data):
	# CC1101 compatible CRC (poly 0x8005, init 0xFFFF, see TI DN502),
	# calculated over length byte + message, before whitening
	crc = 0xFFFF
	for b in data:
		crc ^= b << 8
		for _ in range(8):
			if crc & 0x8000:
				crc = ((crc << 1) ^ 0x8005) & 0xFFFF
			else:
				crc = (crc << 1) & 0xFFFF
	return crc

class Radio(threading.Thread):
	'''Owns the RFM69: receives Moritz frames and transmits queued ones'''

	def __init__(self, rfm, frame_callback):
		threading.Thread.__init__(self, daemon=True)
		self.__rfm = rfm
		self.__frame_callback = frame_callback
		self.__txQueue = deque()
		self.__txLock = threading.Lock()
		self.__radioLock = threading.Lock()
		self.__autoAck = b"\0\0\0"
		self.__fakeWall = b"\0\0\0"
		self.__credit = 900.0
		self.__creditTime = time.monotonic()
		self.__creditLock = threading.Lock()
		self.__lastSend = 0.0

	def configure_ack(self, address, fake_wall=False):
		if fake_wall:
			self.__fakeWall = bytes(address)
		else:
			self.__autoAck = bytes(address)

	def __update_credit(self):
		now = time.monotonic()
		self.__credit = min(900.0, self.__credit + now - self.__creditTime)
		self.__creditTime = now

	def send_budget(self):
		if not CREDIT_LIMIT_ENABLED:
			return 900
		with self.__creditLock:
			self.__update_credit()
			return int(self.__credit)

	def transmit(self, frame, long_preamble=True):
		'''Queue frame (length byte + message, without CRC) for transmission.
		Called from the TCP client threads.'''
		with self.__txLock:
			request = Transmission(list(frame), long_preamble)
			self.__txQueue.append(request)
			for _ in range(5):
				if request.done.is_set():
					return request.sent
				with self.__radioLock:
					if not request.done.is_set():
						self.__rfm.receive_stop()
				if request.done.wait(2):
					return request.sent
			print("ERROR! TX completion timed out", file=sys.stderr)
			return False

	def __send(self, frame, long_preamble):
		preamble = math.ceil(DATARATE * 1000 / 8) if long_preamble else 4
		cost = math.ceil((preamble + 4 + len(frame) + 2) * 8 / (DATARATE * 10))
		with self.__creditLock:
			self.__update_credit()
			if CREDIT_LIMIT_ENABLED:
				if self.__credit < cost:
					print("TX rejected: send budget exhausted", file=sys.stderr)
					return False
				self.__credit -= cost
		time.sleep(max(0, self.__lastSend + 0.02 - time.monotonic()))
		crc = crc16(frame)
		data = list(frame) + [crc >> 8, crc & 0xFF]
		self.__rfm.whiten_ti(data)
		self.__rfm.set_params(Preamble=preamble)
		self.__rfm.send(data)
		self.__lastSend = time.monotonic()
		return True

	def __send_pending(self):
		while True:
			try:
				request = self.__txQueue.popleft()
			except IndexError:
				break
			with self.__radioLock:
				try:
					request.sent = self.__send(request.frame, request.long_preamble)
				finally:
					request.done.set()

	def __handle_frame(self, frame, rssi):
		if len(frame) < 11 or frame[0] != len(frame) - 1:
			print("Invalid RX frame length", file=sys.stderr)
			return
		dst = bytes(frame[7:10])
		auto_ack = any(self.__autoAck) and dst == self.__autoAck and frame[3] in (0x30, 0x40, 0x50)
		fake_wall_ack = any(self.__fakeWall) and dst == self.__fakeWall and frame[0] == 11 and frame[3] == 0x40
		if auto_ack or fake_wall_ack:
			ack = [11, frame[1], 0, 2] + frame[7:10] + frame[4:7] + [0, 0]
			with self.__radioLock:
				time.sleep(0.02)
				if self.__send(ack, False):
					# culfw reports its transmitted automatic ACK as a Z-line.
					self.__frame_callback(ack, 148)
		self.__frame_callback(frame, rssi)

	def run(self):
		while True:
			self.__send_pending()

			self.__rfm.receive_start(0)
			frame = self.__rfm.read_fifo_wait(1)
			rssi = self.__rfm.read_rssi_value() # while frame is still coming in
			if frame:
				framelen = frame[0] ^ 0xFF # invert due to whitening
				frame += self.__rfm.read_fifo_wait(framelen + 2) # message + CRC
			self.__rfm.receive_end()

			if not frame:
				continue # receive was interrupted for a transmission
			framelen = frame[0] ^ 0xFF
			if len(frame) != framelen + 3:
				continue

			self.__rfm.whiten_ti(frame)
			rxcrc = frame[-2] << 8 | frame[-1]
			calccrc = crc16(frame[:-2])
			if rxcrc != calccrc:
				print("RX CRC error (got %04X, calc %04X), dropping frame" % (rxcrc, calccrc), file=sys.stderr)
				continue
			self.__handle_frame(frame[:-2], rssi)

class CulServer(threading.Thread):
	'''TCP server speaking the MAX! via CUL command subset'''

	def __init__(self, port):
		threading.Thread.__init__(self, daemon=True)
		self.radio = None # set by main before start()
		self.__clients = {}
		self.__sendLock = threading.Lock()
		self.__lock = threading.Lock()
		self.__srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.__srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.__srv.bind(("", port))
		self.__srv.listen(4)

	def run(self):
		while True:
			conn, addr = self.__srv.accept()
			print("Client connected: %s:%d" % addr)
			with self.__lock:
				self.__clients[conn] = 0
			t = threading.Thread(target=self.__client_loop, args=(conn, addr), daemon=True)
			t.start()

	def send_frame(self, frame, rssi_raw):
		'''Broadcast a received RF frame as culfw Z-line to all clients'''
		rssi = (148 - rssi_raw) & 0xFF # dBm = -raw/2, encoded CC1101 style
		line = "Z" + "".join("%02X" % b for b in frame)
		print("RX: " + line)
		with self.__lock:
			clients = list(self.__clients.items())
		for conn, flags in clients:
			self.__send(conn, line + ("%02X" % rssi if flags & 0x20 else ""))

	def __send(self, conn, line):
		try:
			with self.__sendLock:
				conn.sendall((line + "\r\n").encode())
		except OSError as err:
			print("TCP send error: %s" % err, file=sys.stderr)

	def __client_loop(self, conn, addr):
		buf = b""
		try:
			while True:
				data = conn.recv(1024)
				if not data:
					break
				buf += data
				if len(buf) > 4096:
					self.__send(conn, "ZERR command buffer exceeded")
					break
				while b"\n" in buf:
					line, buf = buf.split(b"\n", 1)
					self.__handle_command(line.decode(errors="replace").strip(), conn)
		except OSError as err:
			print("TCP receive error: %s" % err, file=sys.stderr)
		finally:
			with self.__lock:
				self.__clients.pop(conn, None)
			conn.close()
			print("Client disconnected: %s:%d" % addr)

	def __handle_command(self, line, conn):
		if line == "":
			return

		if line == "V": # version request
			self.__send(conn, VERSION_STRING)

		elif line == "X": # send budget request
			with self.__lock:
				flags = self.__clients[conn]
			self.__send(conn, "%02X  %d" % (flags, self.radio.send_budget()))

		elif len(line) == 3 and line[0] == "X":
			try:
				flags = int(line[1:], 16)
			except ValueError:
				self.__send(conn, "ZERR invalid reporting flags")
				return
			with self.__lock:
				self.__clients[conn] = flags

		elif line.startswith(("Zs", "Zf")):
			try:
				frame = list(bytes.fromhex(line[2:]))
			except ValueError:
				print("Invalid TX command: " + line, file=sys.stderr)
				self.__send(conn, "ZERR invalid TX hex")
				return
			if len(frame) < 11 or frame[0] != len(frame) - 1:
				print("Invalid TX frame length: " + line, file=sys.stderr)
				self.__send(conn, "ZERR invalid TX length")
				return
			print("TX: " + line)
			if not self.radio.transmit(frame, line[1] == "s"):
				self.__send(conn, "ZERR TX failed")

		elif line.startswith(("Za", "Zw")):
			try:
				address = bytes.fromhex(line[2:])
			except ValueError:
				address = b""
			if len(line) != 8 or len(address) != 3:
				print("Invalid ACK address: " + line, file=sys.stderr)
				self.__send(conn, "ZERR invalid ACK address")
				return
			self.radio.configure_ack(address, line[1] == "w")
			print("Configured %s address: %s" % (line[:2], line[2:]))

		elif line == "Zr": # enable Moritz reception (always on here)
			pass

		elif line.startswith("T"): # FHT settings, ignored
			pass

		else:
			print("Unhandled command: " + line, file=sys.stderr)
			self.__send(conn, "ZERR unsupported command")

def open_rfm():
	if raspyrfm_test(2, RFM69):
		print("Found RaspyRFM twin")
		return RaspyRFM(2, RFM69) # when using the RaspyRFM twin
	elif raspyrfm_test(1, RFM69):
		print("Found RaspyRFM single")
		return RaspyRFM(1, RFM69) # when using a single 868 MHz RaspyRFM
	print("No RFM69 module found!")
	sys.exit(1)

def register_mdns(port):
	'''Announce the TCP interface via mDNS, returns the Zeroconf instance'''
	if not MDNS_ENABLED:
		return None
	try:
		from zeroconf import Zeroconf, ServiceInfo
	except ImportError:
		print("zeroconf not installed, mDNS announcement disabled", file=sys.stderr)
		return None
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		s.connect(("192.0.2.1", 53)) # no traffic sent, only picks the outbound interface
		address = s.getsockname()[0]
	except OSError as err:
		print("mDNS announcement disabled, cannot determine own IP: %s" % err, file=sys.stderr)
		return None
	finally:
		s.close()
	hostname = socket.gethostname().split(".")[0]
	info = ServiceInfo(
		MDNS_SERVICE_TYPE,
		hostname + "." + MDNS_SERVICE_TYPE,
		addresses=[socket.inet_aton(address)],
		port=port,
		server=hostname + ".local.",
	)
	zc = Zeroconf()
	zc.register_service(info)
	print("mDNS: announcing %s on %s:%d" % (MDNS_SERVICE_TYPE, address, port))
	return zc

def main():
	rfm = open_rfm()
	rfm.set_params(
		Freq = 868.300, # MHz center frequency
		ModulationType = rfm69.FSK, # modulation
		Datarate = DATARATE, # kbit/s baudrate
		Deviation = 19.042, # kHz frequency deviation
		SyncPattern = [0xc6, 0x26, 0xc6, 0x26], # syncword
		Bandwidth = 150, # kHz bandwidth
		RssiThresh = -105, # dBm RSSI threshold
	)

	server = CulServer(TCP_PORT)
	radio = Radio(rfm, server.send_frame)
	server.radio = radio
	radio.start()
	server.start()
	print("culfw emulation listening on port %d" % TCP_PORT)
	zc = register_mdns(TCP_PORT)

	try:
		while True:
			time.sleep(1)
	except KeyboardInterrupt:
		pass
	finally:
		if zc is not None:
			zc.close()

if __name__ == "__main__":
	main()
