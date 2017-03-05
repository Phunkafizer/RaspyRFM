#!/usr/bin/env python2.7

import socket
import rfm69
import sys

UDP_IP = "0.0.0.0"
UDP_PORT = 49880
HELLO_MESSAGE = "HCGW:VC:Seegel Systeme;MC:RaspyRFM;FW:1.00;IP:192.168.2.124;;"

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))

#sock.sendto("TXP:0,0,10,20000,350,25,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,1,3,1,3,3,1,1,17;", ("192.168.178.51", 49880))
#sys.exit(0)

rfm = rfm69.Rfm69()
rfm.SetParams(
    Freq = 433.92,
    TXPower = 13,
    ModulationType = rfm69.OOK,
    SyncPattern = [],
    RssiThresh = -72
    )
 
while True:
  data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
  #data = "TXP:0,0,6,5950,350,25,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,3,1,1,3,1,3,1,3,3,1,1,17;"
  #addr = ("123", 5)
  print "received message:", data, "from ", addr

  msg = str(data).split(":")

  if msg[0] == "SEARCH HCGW":
    sock.sendto(HELLO_MESSAGE, addr)
    print "Hello message"

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
    print "bitleft: ", bitleft

    print "reps: ", rep
    print "Pulse data", pulsedata
    print "bin:", bindata
    rfm.SetParams(Datarate = 1000.0 / steplen)
    rfm.SendPacket(bindata * rep)
