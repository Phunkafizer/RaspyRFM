#!/usr/bin/env python

import socket
from raspyrfm import *
import sys

UDP_IP = "0.0.0.0"
UDP_PORT = 49880
HELLO_MESSAGE = "HCGW:VC:Seegel Systeme;MC:RaspyRFM;FW:1.00;IP:0.0.0.0;;"

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))

rfm = RaspyRFM(1, RFM69)
rfm.set_params(
    Freq = 433.92,
    TxPower = 13,
    ModulationType = rfm69.OOK,
    SyncPattern = [],
    )

print("Listening...")
while True:
  data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
  print("received message from " + addr[0] + ': ' + str(data))
  msg = str(data).split(":")

  if msg[0] == "SEARCH HCGW":
    print("Hello message")
    sock.sendto(HELLO_MESSAGE, addr)

  if msg[0] == "TXP":
    msg[1] = msg[1].replace(";", "")
    cmd = msg[1].split(",")
    rep = int(cmd[2])
    pauselen = int(cmd[3])
    steplen = int(cmd[4])
    numpulse = int(cmd[5])
    pulsedata = cmd[6:]
    pulsedata[numpulse * 2 - 1] = int(pulsedata[numpulse * 2 - 1]) + pauselen / steplen

    bindata = []
    bit = True
    numbit = 0
    bitleft = 0
    for i in range(numpulse * 2):
      for bits in range(int(pulsedata[i])):
        if bitleft == 0:
          bitleft = 8
          bindata.append(0x00)

        bindata[len(bindata) - 1] <<= 1
        if bit:
          bindata[len(bindata) - 1] |= 0x01
        bitleft -= 1
      bit = not bit
    for i in range(bitleft):
      bindata[len(bindata) - 1] <<= 1

    rfm.set_params(Datarate = 1000.0 / steplen)
    rfm.send(bindata * rep)
