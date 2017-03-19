#!/usr/bin/env python2.7

from rfm69 import Rfm69
import rfm69
import re

rfm = Rfm69()
rfm.SetParams(
    Freq = 433.92,
    Datarate = 2.666666,
    TXPower = 13,
    ModulationType = rfm69.OOK,
    SyncPattern = []
    )

#Frame generation
def MakeFrame(code, rep):
    data = [0x80, 0x00, 0x00, 0x00] #sync
    b = 0;
    data = []
    for c in code:
        if c == '0':
            data.append(0x88)
        elif c == '1':
            data.append(0xEE)
        elif c == 'F' or c == 'f':
            data.append(0x8E)
    data += [0x80, 0x00, 0x00, 0x00] #sync
        
    return data * rep

def usage():
    print "usage: xx2262.py <CODE>" #12-digit code 12 * ['0' | '1' | 'f']
    print "Example: sudo ./intertechno.py 0FF0F0F00FF0"
    sys.exit(1)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        usage()

    if re.match('[01fF]{12}$', sys.argv[1]) is None:
        print "Invalid code"
        usage()

    data = MakeFrame(sys.argv[1], 5)
    rfm.SendPacket(data)
