
def MakeFrame(code, rep):
	data = [0x08, 0x00] #sync
	for c in code:
		if c == '0':
			data.append(0xA0)
		elif c == '1':
			data.append(0x82)
	data += [0x80, 0x00, 0x00, 0x00, 0x00]	
	return data * rep
