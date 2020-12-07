#!/usr/bin/env python2.7

import socket
import threading
from raspyrfm import *
import rcprotocols
import json
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
args = parser.parse_args()

srvsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srvsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srvsock.bind(('', 1989))
srvsock.listen(5)

clients = []

def rxcb(dec, train):
    payload = None
    if dec is None:
        payload = {"raw": train}
    else:
        if len(dec) > 0:
            payload = {"decode": dec, "raw": train}

	print(payload)
    if payload is not None:
        for client in clients:
            client.send(payload)


if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

rctrx = rcprotocols.RcTransceiver(args.module, args.frequency, rxcb)

lock = threading.Lock() 

class clientthread(threading.Thread):
    def __init__(self, socket):
        self.__socket = socket
        threading.Thread.__init__(self)

    def send(self, obj):
        self.__socket.send(json.dumps(obj))

    def run(self):
        while True:
            chunk = self.__socket.recv(1024)
            if len(chunk) == 0:
                del self.__socket
                break
            try:
                #print(chunk)
                lock.acquire()
                d = json.loads(chunk)
                rctrx.send(d["protocol"], d["params"])
            except:
                pass
            lock.release()
        clients.remove(self)

while True:
    (client, address) = srvsock.accept()
    ct = clientthread(client)
    ct.daemon = True
    ct.start()
    clients.append(ct)