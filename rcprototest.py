#!/usr/bin/env python3

"""
sends a command using the Home Assistant rf-protocols module
install: pip install rf-protocols
"""

from raspyrfm import *
from rf_protocols import ModulationType, RadioFrequencyCommand
from rf_protocols.commands.kaku import KakuCommand
from rf_protocols.commands.fs20 import FS20Command, FS20CommandType
import time

def send_command(cmd):
	DATARATE = 20.0 # kbit/s
	PULSEWIDTHUS = 1/DATARATE*1000

	if (cmd.frequency > 500E6) and raspyrfm_test(2, RFM69):
		mod = 2
	else:
		mod = 1

	print(F"Create RFM #{mod} {cmd.frequency/1E6} MHz")
	rfm = RaspyRFM(mod, RFM69)
	rfm.set_params(
		Freq = cmd.frequency / 1E6, # MHz
		Datarate = DATARATE,
		SyncPattern = [],
		ModulationType = rfm69.OOK,
		Preamble = 0,
		TxPower = 13
	)

	timings = cmd.get_raw_timings()
	print("Pulsetrain:", timings)

	stream = bytearray()
	current_byte = 0
	bit_count = 0

	for _ in range(6):
		for pulse in timings:
		    num_bits = round(abs(pulse) / PULSEWIDTHUS)
		    bit_val = 1 if pulse > 0 else 0
		    for _ in range(num_bits):
		        current_byte = (current_byte << 1) | bit_val
		        bit_count += 1

		        if bit_count == 8:
		            stream.append(current_byte)
		            current_byte = 0
		            bit_count = 0

	if bit_count > 0:
	    current_byte <<= (8 - bit_count)
	    stream.append(current_byte)

	rfm.send(stream)
	time.sleep(0.3)



#cmd = FS20Command(housecode=1234, address=4, command=FS20CommandType.ON_100_PERCENT)
#send_command(cmd)
#time.sleep(2)

#cmd = FS20Command(housecode=1234, address=4, command=FS20CommandType.OFF)
#send_command(cmd)
#time.sleep(2)

cmd = FS20Command(housecode="11214213", address=4, command=FS20CommandType.DIM_UP, extension=16)
send_command(cmd)
