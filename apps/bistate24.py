#!/usr/bin/env python2.7

import re

def Decode(pulses):
	if len(pulses) != 50:
		return
		
	sym = ""
	s = 0
	for p in pulses:
		if (p >= 200) and (p <= 450):
			sym += 's'
			s += p
		elif (p >= 600) and (p <= 1350):
			sym += 'l'
			s += p
		else:
			sym += '?'
			
	code = ""
	for i in range(24):
		if sym[:2] == 'sl':
			code += "0"
		elif sym[:2] == "ls":
			code += "1"
		else:
			return
		sym = sym[2:]
	
	return ("bistate24", code, int(round(s / (24.0 * 4 + 1))))
		
def Encode(args):
	code = ' '.join(args)
	if re.match("^[01]{24}$", code):
		data = []
		d = 0
		pos = 4
		for c in code:
			d |= (0x8 if c == '0' else 0xe) << pos
			if pos == 0:
				data.append(d)
				d = 0
				pos = 4
			else:
				pos = 0

		data += [0x80, 0x00, 0x00, 0x00]
		return (data, 5, 330)

	elif re.match("^([01]{20}) ([A])$", code):
		g = re.match("^([01]{20}) ([ABCD])$", code).groups()
		bits = g[0]
		if g[1] == 'A':
			bits += '0001'
		elif g[1] == 'B':
			bits += '0010'
		elif g[1] == 'C':
			bits += '0100'
		elif g[1] == 'D':
			bits += '1000'
		return Encode([bits])
