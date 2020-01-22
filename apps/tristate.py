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
	temp = sym
	for i in range(12):
		if temp[:4] == 'slsl':
			code += "0"
		elif temp[:4] == "lsls":
			code += "1"
		elif temp[:4] == "slls":
			code += "f"
		else:
			return
		temp = temp[4:]
		
	return ("tristate", code, int(round(s / (12.0 * 8 + 1))))

def encodeBits(val, num):
    result = ''
    for i in range(num):
        if (val & 0x01):
            result += 'F'
        else:
            result += '0'
        val >>= 1
    return result
	
def Encode(args):
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