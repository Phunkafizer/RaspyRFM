import re
from argparse import ArgumentParser
from raspyrfm import *
import threading

class RcProtocol:
	def __init__(self):
		self.__numbits = 0
		self._ookdata = bytearray()
		self.__bbuf = 0
		self.__bval = 0
		self._parser = ArgumentParser()

		sympulses = []
		for i in self._symbols:
			sympulses += self._symbols[i]
		sympulses.sort(reverse=True)
		i = 0
		while i<len(sympulses) - 1:
			if (sympulses[i] == sympulses[i+1]):
				del sympulses[i]
			else:
				i += 1
		p1 = sympulses.pop(0)
		p2 = sympulses.pop(0)
		f = (1.0 * p1 / p2 - 1) / (1.0 * p1/p2 + 2)
		self._minwidth = self._timebase - self._timebase * f
		self._maxwidth = self._timebase + self._timebase * f
		
	def _reset(self):
		self.__numbits = 0
		self._ookdata = bytearray()
		self.__bbuf = 0
		self.__bval = 0

	def _add_pulses(self, numbits):
		for num in numbits:
			self.__bval ^= 1
			for i in range(num):
				self.__bbuf <<= 1
				self.__bbuf |= self.__bval
				self.__numbits += 1
				if self.__numbits == 8:
					self._ookdata.append(self.__bbuf)
					self.__bbuf = 0
					self.__numbits = 0
					
	def _add_finish(self):
		if (self.__numbits > 0):
			self.__bval ^= 1
			self._add_pulses([8 - self.__numbits])

	def _add_symbols(self, symbols):
		for s in symbols:
			sym = self._symbols[s]
			for pulse in sym:
				self._add_pulses([pulse])

	def _match_symbol(self, pulsetrain, symbol):
		if len(pulsetrain) != len(symbol):
			return False

		sumpulse = 0
		sumstep = 0
		for i, v in enumerate(symbol):
			if not (self._minwidth <= 1.0 * pulsetrain[i] / v <= self._maxwidth):
				return
			sumpulse += pulsetrain[i]
			sumstep += v
		return (sumpulse, sumstep)

	def _decode_symbols(self, pulsetrain):
		#match symbols
		dec = ""
		pos = 0
		sumpulse = 0
		sumstep = 0
		while pos < len(pulsetrain):	
			match = None
			for s in self._symbols:
				slen = len(self._symbols[s])
				match = self._match_symbol(pulsetrain[pos:pos+slen], self._symbols[s])
				if match:
					dec += s
					pos += slen
					sumpulse += match[0]
					sumstep += match[1]
					break

			if not match:
				return None, None

		if re.match("^" + self._pattern + "$", dec):
			return dec, int(1.0 * sumpulse / sumstep)
			
		return None, None

	def decode(self, pulsetrain):
		pass
		
	def encode(self, args):
		pass

class IT32(RcProtocol): #switch1
	def __init__(self):
		self._name = "it32"
		self._timebase = 250
		self._repetitions = 4
		self._pattern = "[01]{32}"
		self._symbols = {
			'0': [1, 1, 1, 5],
			'1': [1, 5, 1, 1],
		}
		RcProtocol.__init__(self)
		self._parser.add_argument("-c", "--code")
		self._parser.add_argument("-i", "--id", type=int, required=True)
		self._parser.add_argument("-u", "--unit", type=int, required=True)
		self._parser.add_argument("-s", "--state", type=int, required=True)
		
	def __encode(self, code):
		self._reset()
		self._add_pulses([1, 11])
		self._add_symbols(code)
		self._add_pulses([1, 39])
		self._add_finish()
		return self._ookdata
		
	def encode(self, args):
		if hasattr(args, "code") and args.code:
			if re.match("^[01]{32}$", args.code):
				return self.__encode(args.code)
				
		code = ""
		code += "{:026b}".format(args.id)
		code += "0" #group
		code += "1" if args.state != 0 else "0"
		code += "{:04b}".format(args.unit - 1)
		return self.__encode(code)

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
				"id": int(code[0:26], 2),
				"group": int(code[26:27], 2),
				"state": int(code[27:28], 2),
				"unit": int(code[28:32], 2) + 1,
			}

class ITTristate(RcProtocol): #old intertechno systems
	def __init__(self):
		self._name = "ittristate"
		self._timebase = 300
		self._repetitions = 4
		self._pattern = "[01fF]{12}"
		self._symbols = { 
			'0': [1, 4, 1, 4],
			'1': [4, 1, 4, 1],
			'f': [1, 4, 4, 1],
			'F': [1, 4, 4, 1],
		}
		RcProtocol.__init__(self)
		self._parser.add_argument("-c", "--code")
		self._parser.add_argument("-o", "--house")
		self._parser.add_argument("-g", "--group", type=int)
		self._parser.add_argument("-u", "--unit", type=int)
		self._parser.add_argument("-s", "--state", type=int)

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
			}
		
	def __encode(self, code):
		self._reset()
		self._add_symbols(code)
		self._add_pulses([1, 31])
		self._add_finish()
		return self._ookdata
		
	def __encode_int(self, ival, digits):
		code = ""
		for i in range(digits):
			code += "f" if (ival & 0x01) > 0 else "0"
			ival >>= 1
		return code
		
	def encode(self, args):
		if hasattr(args, 'code') and args.code:
			if re.match("^[01Ff]{12}$", args.code):
				return self.__encode(args.code)

		code = ""
		code += self.__encode_int(ord(args.house[0]) - ord('A'), 4)
		if hasattr(args, 'group') and args.group:
			code += self.__encode_int(args.group - 1, 2)
			code += self.__encode_int(args.unit - 1, 2)
		else:
			code += self.__encode_int(args.unit - 1, 4)
		code += "0f"
		code += "ff" if args.state > 0 else "f0"
		return self.__encode(code)
		
class Bistate24(RcProtocol):
	def __init__(self):
		self._name = "bistate24"
		self._timebase = 300
		self._repetitions = 6
		self._pattern = "[01]{24}"
		self._symbols = { 
			'1': [3, 1],
			'0': [1, 3],
		}
		RcProtocol.__init__(self)
		self._parser.add_argument("-c", "--code", required=True)

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
			}

	def encode(self, args):
		self._reset()
		self._add_symbols(args.code)
		self._add_pulses([1, 31])
		self._add_finish()
		return self._ookdata

class Switch15(Bistate24): #e. g. logilight
	def __init__(self):
		Bistate24.__init__(self)
		self._name = "switch15"
		#remove code argument
		carg = self._parser._actions[-1]
		carg.container._remove_action(carg)
		self._parser.add_argument("-i", "--id", type=int, required=True)
		self._parser.add_argument("-u", "--unit", type=int, required=True)
		self._parser.add_argument("-s", "--state", type=int, required=True)

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			state = int(code[20:21])
			unit = int(code[21:24], 2)
			all = False
			if unit == 7:
				unit = 1
			elif unit == 3:
				unit = 2
			elif unit == 5:
				unit = 3
			elif unit == 6:
				unit = 4
			else:
				unit = 0
				state = not state

			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
				"id": int(code[0:20], 2),
				"unit": unit,
				"state": state,
			}

	def encode(self, args):
		self._reset()
		sym = '{:020b}'.format(args.id)

		if args.unit == 1:
			unit = 7
		elif args.unit == 2:
			unit = 3
		elif args.unit == 3:
			unit = 5
		elif args.unit == 4:
			unit = 6
		else:
			raise Exception("invalid unit")
		sym += '1' if args.state > 0 else '0'
		sym += '{:03b}'.format(unit)
		self._add_symbols(sym)
		self._add_pulses([1, 31])
		self._add_finish()
		return self._ookdata
		
class Emylo(Bistate24):
	def __init__(self):
		Bistate24.__init__(self)
		self._name = "emylo"
		#remove code argument
		carg = self._parser._actions[-1]
		carg.container._remove_action(carg)
		self._parser.add_argument("-i", "--id", type=int, required=True)
		self._parser.add_argument("-k", "--key", required=True)

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			key = int(code[20:24], 2)
			if key == 1:
				key = 'A'
			elif key == 2:
				key = 'B' 
			elif key == 4:
				key = 'C'
			elif key == 8:
				key = 'D'
			else:
				return

			return {
				"protocol": self._name,
				"timebase": tb,
				"id": int(code[0:20], 2),
				"key": key,
			}

	def encode(self, args):
		self._reset()
		sym = '{:020b}'.format(args.id)
		if args.key == "A":
			sym += "0001"
		elif args.key == "B":
			sym += "0010"
		elif args.key == "C":
			sym += "0100"
		elif args.key == "D":
			sym += "1000"
		else:
			return

		self._add_symbols(sym)
		self._add_pulses([1, 31])
		self._add_finish()
		return self._ookdata

class FS20(RcProtocol):
	def __init__(self):
		self._name = "fs20"
		self._timebase = 200
		self._repetitions = 4
		self._pattern = "0000000000001[01]{45}"
		self._symbols = { 
			'0': [2, 2],
			'1': [3, 3],
		}
		RcProtocol.__init__(self)
		self._parser.add_argument("-o", "--house", type=int, required=True)
		self._parser.add_argument("-a", "--address", type=int, required=True)
		self._parser.add_argument("-d", "--cmd", type=int, required=True)
		
	def __encode_byte(self, b):
		self._add_symbols('{:08b}'.format(b))
		par = 0
		while b:
			par ^= 1
			b &= b-1
		self._add_symbols('1' if par != 0 else '0')

	def encode(self, args):
		self._reset()
		self._add_symbols("0000000000001")
		self.__encode_byte(args.house >> 8)
		self.__encode_byte(args.house & 0xFF)
		self.__encode_byte(args.address)
		self.__encode_byte(args.cmd)
		q = 0x06 + (args.house >> 8) + (args.house & 0xFF) + args.address + args.cmd
		self.__encode_byte(q & 0xFF)
		self._add_pulses([1, 100])
		self._add_finish()
		return self._ookdata

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
				"housecode": int(code[13:21] + code[22:30] , 2),
				"address": int(code[31:39], 2),
				"cmd": int(code[40:48], 2),
			}

class Voltcraft(RcProtocol):
	def __init__(self):
		self._name = "voltcraft"
		self._timebase = 600
		self._repetitions = 4
		self._pattern = "[01]{20}"
		self._symbols = { 
			'0': [1, 2],
			'1': [2, 1],
		}
		RcProtocol.__init__(self)
		self._parser.add_argument("-i", "--id", type=int, required=True)
		self._parser.add_argument("-u", "--unit", type=int, required=True)
		self._parser.add_argument("-s", "--state", type=int, required=True)

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[1:-1])
		if code:
			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
				"id": int(code[0:12][::-1], 2),
				"unit": int(code[12:14][::-1], 2) + 1,
				"state": int(code[14:17][::-1], 2) #0=off, 1=alloff, 2=on, 3=allon, 5=bright, 7=dim 
			}
		
	def encode(self, args):
		if not (args.state in [0, 2]):
			unit = 3
		else:
			unit = args.unit -1
		symbols = "{:012b}".format(args.id)[::-1]
		symbols += "{:02b}".format(unit)[::-1]
		symbols += "{:03b}".format(args.state)[::-1]
		symbols += "0"
		symbols += "1" if (symbols[12] == "1") ^ (symbols[14] == "1") ^ (symbols[16] == "1") else "0"
		symbols += "1" if (symbols[13] == "1") ^ (symbols[15] == "1") ^ (symbols[17] == "1") else "0"
		self._reset()
		self._add_pulses([1])
		self._add_symbols(symbols)
		self._add_pulses([132])
		self._add_finish()
		return self._ookdata
		
class PDM32(RcProtocol): 
	def __init__(self):
		self._name = "pdm32"
		self._timebase = 600
		self._repetitions = 6
		self._pattern = "[01]{32}"
		self._symbols = { 
			'1': [1, 2],
			'0': [2, 1],
		}
		RcProtocol.__init__(self)
		self._parser.add_argument("-c", "--code")

	def decode(self, pulsetrain):
		code, tb = self._decode_symbols(pulsetrain[0:-2])
		if code:
			return {
				"protocol": self._name,
				"code": code,
				"timebase": tb,
			}

	def encode(self, args):
		self._reset()
		self._add_symbols(args.code)
		self._add_pulses([1, 11])
		self._add_finish()
		return self._ookdata

protocols = [
	IT32(),
	Switch15(),
	ITTristate(),
	Voltcraft(),
	FS20(),
	Emylo(),
	PDM32(),
	Bistate24(),
]

def encode(protocol, args):
	for p in protocols:
		if (protocol):
			if p._name == protocol:
				return (p.encode(p._parser.parse_args(args)), p._timebase, p._repetitions)

class RCStruct:
    def __init__(self, **entries):
        self.__dict__.update(entries)

def encode_dict(dict):
	s = RCStruct(**dict)
	for p in protocols:
		if p._name == s.protocol:
			return (p.encode(s), p._timebase, p._repetitions)

def decode(pulsetrain):
	dec = None
	res = []
	for p in protocols:
		dec = p.decode(pulsetrain)
		if dec:
			res.append(dec)

	if len(res) > 0:
		return res
		
class PulseReceiver(threading.Thread):
	def __init__(self, module):
		self.__trainbuf = []
		self.__rfm = RaspyRFM(module, RFM69)
		self.__rfm.set_params(
			Freq = 433.92, #MHz
			Datarate = 20.0, #kbit/s
			Bandwidth = 300, #kHz
			SyncPattern = [],
			RssiThresh = -105, #dBm
			ModulationType = rfm69.OOK,
			OokThreshType = 1, #peak thresh
			OokPeakThreshDec = 3,
			Preamble = 0,
			TxPower = 13
		)
		threading.Thread.__init__(self)
		self.daemon = True
		self.start()
		
	def getEvents(self):
		if len(self.__trainbuf) > 0:
			train = self.__trainbuf.pop()
			for i, v in enumerate(train):
				train[i] = 50 * v;
			return decode(train)
		
	def run(self):
		self.__rfm.start_receive(self.__cb)
	
	def __cb(self, rfm):
		bit = False
		cnt = 1
		train = []
		
		while True:
			fifo = rfm.read_fifo_wait(64)
			ba = bytearray()

			for b in fifo:
				mask = 0x80
				while mask != 0:
					if (b & mask) != 0:
						ba.append(245)
					else:
						ba.append(10)

					if ((b & mask) != 0) == bit:
						cnt += 1
					else:
						if cnt < 3: #<150 us
							train *= 0 #clear
						elif cnt > 50:
							if not bit:
								train.append(cnt)
								if len(train) > 20:
									self.__trainbuf.append(list(train))
							train *= 0 #clear
						elif len(train) > 0 or bit:
							train.append(cnt)
						cnt = 1
						bit = not bit
					mask >>= 1
