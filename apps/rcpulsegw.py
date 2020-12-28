#!/usr/bin/env python

from raspyrfm import *
import rcprotocols
import json
from argparse import ArgumentParser
import apiserver
import time

parser = ArgumentParser()
parser.add_argument("-m", "--module", type=int, metavar="1-4", help=u"RaspyRFM module 1-4", default=1)
parser.add_argument("-f", "--frequency", type=float, help=u"frequency in MHz", default=433.92)
args = parser.parse_args()

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


if not raspyrfm_test(args.module, RFM69):
	print("Error! RaspyRFM not found")
	exit()

rctrx = rcprotocols.RcTransceiver(args.module, args.frequency, rccb)

def apicb(data):
    print("TX", data)
    try:
        rctrx.send(data["protocol"], data["params"])
    except:
        pass

apisrv = apiserver.ApiServer(1989, apicb)

while True:
    time.sleep(1)
