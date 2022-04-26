#!/usr/bin/env python

from config import *

while 1:
        data = rfm.receive(16)
        print(data)
