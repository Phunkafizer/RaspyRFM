#!/usr/bin/env python

import sys, time, wave, struct, threading, argparse
from raspyrfm import *
import rcprotocols

DATARATE = 20.0 #kbit/s
rfm = RaspyRFM(1, RFM69)
rfm.set_params(
	Freq = 433.92, #MHz
        Datarate = DATARATE,
        SyncPattern = [],
        ModulationType = rfm69.OOK,
        TxPower = 13
)
rcraw = rcprotocols.RcRaw(round(1000 / DATARATE))


data = rcraw.build_raw([
	300, 1100, 300, 1100, 300, 1100, 300, 1100,
	300, 1100, 300, 1100, 300, 1100, 300, 1100,
	300, 1100, 300, 1100, 300, 1100, 300, 1100,
	300, 1100, 300, 1100, 300, 1100, 300, 1100,
	300, 1100, 300, 1100, 300, 1100, 950, 450,
	300, 1100, 1000, 400, 300, 1100, 1000, 400,
	300, 11100
], 3)

rfm.send(data)
