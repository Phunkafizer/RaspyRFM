#!/usr/bin/env python2.7

import socket
import time
import rfm69
from rfm69 import Rfm69
import xx2262
import it32
import threading

PORT = 5052

rfm = Rfm69(1, 24)
rfm.SetParams(
	Freq = 868.300, #MHz center frequency
	ModulationType = rfm69.FSK, #modulation
	Datarate = 9.992, #kbit/s baudrate
	Deviation = 19.042, #kHz frequency deviation -> OBW = 48 kHz, h = 3.81
	SyncPattern = [0xc6, 0x26, 0xc6, 0x26], #syncword
	Bandwidth = 100, #kHz bandwidth (101.5)
	RssiThresh = -100, #-100 dB RSSI threshold
	Preamble = 1700
)

connections = []

def maxPrint(frame):	
	x = {}
	x['cnt'] = frame[1]
	x['flag'] = hex(frame[2])
	x['type'] = hex(frame[3])
	x['src'] = hex(frame[4] << 16 | frame[5] << 8 | frame[6])
	x['dst'] = hex(frame[7] << 16 | frame[8] << 8 | frame[9])
	x['grp'] = frame[10]
	x['pay'] = []
	for i in range(frame[0] - 10):
		x['pay'].append(frame[i + 11])

	info = ""
	if x['type'] == '0x42':
		info = str(x['pay'][0] / 2.0) + ' / ' + str(x['pay'][1] / 10.0)

	print(x['src'] + "->" + x['dst'] + " type " + x['type'] + ':', x['pay'], info)
	
class Connection(threading.Thread):
	def __init__(self, sock, rfm):
		self._socket = sock
		self._rfm = rfm
		self.__housecode = "0000"
		self.__rxflags = 0
		threading.Thread.__init__(self)

	def sendHost(self, line):
		#print("TO FHEM: " + line)
		self._socket.send(line + "\n")

	def sendRF(self, symbolTime, data):
		self._rfm.SetParams(Datarate = 1E3/symbolTime)
		self._rfm.SendPacket(data)
		
	def run(self):
		while True:
			data = self._socket.recv(1024)
			if not data:
				break
				
			lines = str.splitlines(data)

			for line in lines:
				print("FROM FHEM: " + line)

				if line == 'V':
					self.sendHost("V 1.0 CULEMU")

				elif line[:1] == "X":
					line = line[1:]
					if len(line) > 0:
						self.__rxflags = int(line, 16)
					else:
						self.sendHost("X" + format(self.__rxflags, "02X") + format(900, "05d"))	
					pass

				elif line[:2] == "is":
					self.sendHost(line)

					line = line[2:]
					if len(line) == 12:
						frame = xx2262.MakeFrame(line, 5)
						self.sendRF(375, frame)
					elif len(line) == 32:
						frame = it32.MakeFrame(line, 5)
						self.sendRF(275, frame)

				elif line[:3] == "T01":
					if len(line) > 3:
						self.__housecode = line[3:]
					else:
						self.sendHost(self.__housecode)
						
				elif line[:2] == "Zr":
					pass
					
				elif line[:2] == "Zs":
					line = line[2:]
					frame = bytearray.fromhex(line)
					#maxPrint(frame)
					rfm.WhitenTI(frame)
					self._rfm.SendPacket(frame)
					print("TX!")
				else:
					self.sendHost("? (? is unknown) Use one of C F R T V W X e f l t x Z")

		print "destroy connection"
		connections.remove(self)
		del self

class CulEmu(threading.Thread):
	def __init__(self, rfm, port):
		self._rfm = rfm
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._sock.bind(('', port))
		self._sock.listen(4)
		threading.Thread.__init__(self)

	def run(self):
		while True:
			conn, addr = self._sock.accept()
			print "New connection from", addr
			c = Connection(conn, self._rfm) 
			c.start()
			connections.append(c)
			
	def sendHost(self, s):
		for c in connections:
			c.sendHost(s)

rxevent = threading.Event()
rxmutex = threading.Lock()
rxbuf = []

cul = CulEmu(rfm, PORT)
cul.daemon = True
cul.start()

class RxThread(threading.Thread):
	def __init__(self, rfm):
		self.__rfm = rfm
		threading.Thread.__init__(self)
		
	def callback(self):
		lfsr = 0x1ff
		frame = rfm.ReadFifoWait(1)
		len = frame[0] ^ 0xFF #invert due to whitening
		
		frame += rfm.ReadFifoWait(len)
		
		rxmutex.acquire()
		rxbuf.append(frame)
		rxmutex.release()
		rxevent.set()
		
		return
		
	def run(self):
		while True:
			rxevent.wait()
			left = True
			while left:
				rxmutex.acquire()
				rxevent.clear()
				frame = rxbuf.pop(0)
				left = len(rxbuf) > 0
				rxmutex.release()
				
				rfm.WhitenTI(frame)
				s = "Z"
				for b in frame:
					s += format(b, "02X")
				s += "20"
				cul.sendHost(s)
				#maxPrint(frame)
				
				if not left:
					break			

rxthread = RxThread(rfm)
rxthread.daemon = True
rxthread.start()
		
while True:
	data = rfm.StartRx(rxthread.callback)
