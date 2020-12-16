#!/usr/bin/env python

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

    if payload is not None:
        print("RX", payload)
        s = json.dumps(payload) + "\n"
        for client in clients:
            client.send(s)


if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

rctrx = rcprotocols.RcTransceiver(args.module, args.frequency, rxcb)
lock = threading.Lock()

class clientthread(threading.Thread):
    def __init__(self, socket):
        self.__socket = socket
        threading.Thread.__init__(self)

    def send(self, s):
        self.__socket.sendall(s.encode())

    def run(self):
        buf = ""
        while True:
            chunk = self.__socket.recv(32).decode()
            if len(chunk) == 0:
                del self.__socket
                break
            lock.acquire()
            try:
                buf += chunk
                while "\n" in buf:
                    line = buf[:buf.find("\n")]
                    buf = buf[buf.find("\n") + 1:]
                    d = json.loads(line)
                    print("TX", d)
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
