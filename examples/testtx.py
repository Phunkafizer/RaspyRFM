#!/usr/bin/env python

from config import *
import time

while True:
	print("Sending testdata...")
	rfm.send([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
	time.sleep(2)
