#!/usr/bin/env python2.7

import socket
import time

UDP_IP = "0.0.0.0"
UDP_PORT = 49880
HELLO_MESSAGE = "HCGW:VC:Seegel Systeme;MC:RaspyRFM;FW:1.00;IP:192.168.2.124;;"

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))
 
while True:
  data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
  msg = str(data).split(":")

  print "received message:", msg, "from ", addr

  if msg[0] == "SEARCH HCGW":
    sock.sendto(HELLO_MESSAGE, addr)
    print "Hello message"

  if msg[0] == "TXP":
    cmd = msg[1].split(",")
    print "Command: ", cmd
