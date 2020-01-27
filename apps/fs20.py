#!/usr/bin/env python2.7

import re

PROTOCOL = "FS20"

def __parse_byte(bits):
	i = int(bits, 2)
	cnt = 0
	tmp = i
	while tmp > 0:
		cnt += 1
		tmp &= tmp - 1
	if (cnt & 1) == 0:
		return i>>1
	else:
		return -1
		
def Decode(pulses):
	if len(pulses) != 118:
		print(len(pulses), pulses)
		return
		
	sym = ""
	s = 0
	for p in pulses:
		if (p >= 300) and (p <= 500):
			sym += 's'
			s += p
		elif (p > 500) and (p <= 750):
			sym += 'l'
			s += p
		else:
			sym += '?'
			
	bits = ""
	for i in range(59):
		if sym[:2] == 'ss':
			bits += "0"
		elif sym[:2] == "ll":
			bits += "1"
		else:
			bits +="?"
		sym = sym[2:]
		
	print(bits)
	#check for sync sequence
	if bits[:13] != "0000000000001":
		return
	bits = bits[13:] #strip off sync sequence 
	
	by = []
	while len(bits) >= 9:
		by.append(__parse_byte(bits[:9]))
		bits = bits[9:]
		
	#check checksum
	cs = 6
	for i in range(len(by) - 1):
		cs += by[i]
	cs = by[-1:][0] - (cs & 0xff)
	if (cs > 2) or (cs < 0):
		return
		
	ret = {
		"protocol": PROTOCOL,
		"housecode": "{:04X}".format((by[0] << 8) | by[1]),
		"address": "{:02X}".format(by[2]),
		"command": "{:02X}".format(by[3]) if len(by) == 5 else "{:04X}".format(by[3] << 8 | by[4])
	}
	print(ret)
	
	return
	return ("fs20", bits, int(round(100 / (12.0 * 8 + 1))))
	
def Encode(args):
	da = []
	bp = [0]
	bv = [0]
	def add_pulse(val, length):
		for i in range(length):
			bp[0] += 1
			bv[0] <<= 1
			bv[0] |= val
			if bp[0] == 8:
				da.append(bv[0])
				bv[0] = 0
				bp[0] = 0
				
	def add_bit(b):
		if b == 0:
			add_pulse(1, 2)
			add_pulse(0, 2)
		else:
			add_pulse(1, 3)
			add_pulse(0, 3)
		
	def add_byte(by):
		par = 0
		mask = 0x80
		while (mask):
			add_bit(by & mask)
			par >>= 1
			par ^= (by & mask)
			mask >>= 1
		add_bit(par)
	
	#add sync pattern
	for i in range(12):
		add_bit(0)
	add_bit(1)
	
	hc = int(args[0], 16)
	adr = int(args[1], 16)
	cmd = int(args[2], 16)
	#calculate checksum
	q = (6 + (hc >> 8) + (hc & 0xFF) + adr + (cmd >> 8) + (cmd & 0xFF)) & 0xff
	#add housecode
	add_byte(hc >> 8)
	add_byte(hc & 0xFF)
	#add address
	add_byte(adr)
	#add command
	add_byte(cmd)
	#add checksum
	add_byte(q)
	#add EOT
	add_bit(0)
	add_pulse(0, 33)
	if bp[0] > 0:
		add_pulse(0, 8-bp[0])
	return (da, 3, 200)
		
	code = ' '.join(args)
	if re.match("^[01Ff]{12}$", code):
		data = []
		for c in code:
			if c == '0':
				data.append(0x88)
			elif c == '1':
				data.append(0xEE)
			elif c in ['F', 'f']:
				data.append(0x8E)
		data += [0x80, 0x00, 0x00, 0x00] #sync
	
		return (data, 5, 360)
	
	elif re.match('^[A-P] [1-4] [1-4] (on|off)$', code):
		g = re.match('^([A-P]) ([1-4]) ([1-4]) (on|off)$', code).groups()
		tristate = ""
		tristate += encodeBits(ord(g[0]) - ord('A'), 4) #housecode
		tristate += encodeBits(ord(g[2]) - 1, 2) #channel
		tristate += encodeBits(ord(g[1]) - 1, 2) #group
		tristate += "0F"
		tristate += 'FF' if g[3] == 'on' else 'F0'
		return Encode([tristate])
		
	elif re.match('^([01]{5}) ([1-4]) (on|off)$', code): #Brennenstuhl
		g = re.match('^([01]{5}) ([1-4]) (on|off)$', code).groups()
		tristate = ""
		for c in g[0]:
			tristate += '0' if c == '1' else 'F'
		for i in range(4):
			tristate += '0' if int(g[1]) - 1 == i else 'F'
		tristate += 'F'
		tristate += '0F' if g[2] == 'on' else 'F0'
		return Encode([tristate])
		
	elif re.match('^[1-4] [1-4] (on|off)$', code):
		g = re.match('^([1-4]) ([1-4]) (on|off)$', code).groups()
		tristate = ""
		for i in range(4):
			tristate += "0" if int(g[0]) - 1 == i else "F"
		for i in range(4):
			tristate += "0" if int(g[1]) - 1 == i else "F"
		tristate += "FFF"
		tristate += 'F' if g[2] == 'on' else '0'
		return Encode([tristate])