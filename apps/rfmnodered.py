#!/usr/bin/env python2.7

import socket
import threading
from raspyrfm import *
import rcprotocols
import json

srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srvsock.bind(('', 1989))
srvsock.listen(5)

rfm = RaspyRFM(1, RFM69)
rfm.set_params(
	Freq = 433.92, #MHz
	Datarate = 20.0, #kbit/s
	Bandwidth = 300, #kHz
	SyncPattern = [],
	RssiThresh = -105, #dBm
	ModulationType = rfm69.OOK,
	OokThreshType = 1, #peak thresh
	OokPeakThreshDec = 3,
	Preamble = 0,
	TxPower = 13
)

lock = threading.Lock() 

class clientthread(threading.Thread):
    def __init__(self, socket):
        self.__socket = socket
        threading.Thread.__init__(self)

    def run(self):
        while True:
            chunk = self.__socket.recv(1024)
            if len(chunk) == 0:
                del self.__socket
                break
            print(chunk)
            try:
                lock.acquire()
                txdata = rcprotocols.encode_dict(json.loads(chunk))
                print(txdata)
                rfm.set_params(
                    SyncPattern = [],
                    Datarate = 1000.0 / txdata[1]
                )
                rfm.send(txdata[0] * txdata[2])
            except:
                pass
            lock.release()

while True:
    (client, address) = srvsock.accept()
    ct = clientthread(client)
    ct.daemon = True
    ct.start()