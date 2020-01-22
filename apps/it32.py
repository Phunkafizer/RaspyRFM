import re

def Decode(pulses):
	if len(pulses) != 130:
		return
		
	sym = ""
	s = 0
	for p in pulses:
		if (p >= 150) and (p <= 500):
			s += p
			sym += 's'
		elif (p >= 1000) and (p <= 1500):
			s += p
			sym += 'l'
		else:
			sym += '?'
	
	it = ""
	temp = sym
	for i in range(32):
		if temp[:4] == 'sssl':
			it += "0"
		elif temp[:4] == "slss":
			it += "1"
		else:
			return
		temp = temp[4:]
	return("it32", it, int(round(s / (32.0 * 8 + 1))))

def Encode(args):
	code = ' '.join(args)
	if re.match("^[01]{32}$", code):	
		data = [0x08, 0x00] #sync
		for c in args[0]:
			if c == '0':
				data.append(0xA0)
			elif c == '1':
				data.append(0x82)
		data += [0x80, 0x00, 0x00, 0x00, 0x00]	
		return (data, 6, 275)
		
	elif re.match("^[01]{26} ([0][1-9]|[1-9]|[1][0-6]) (on|off)$", code):
		g = re.match("^([01]{26}) ([0][1-9]|[1-9]|[1][0-6]) (on|off)$", code).groups()
		bits = g[0] + '0'
		bits += '1' if g[2] == 'on' else '0'
		bits += "{0:04b}".format(int(g[1]) - 1) 
		return Encode([bits])