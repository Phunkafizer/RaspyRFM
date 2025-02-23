import re
from argparse import ArgumentParser
from raspyrfm import *
import threading
import time
import json
import collections

RXDATARATE = 20.0 #kbit/s
PULSEWIDTHUS = 1/RXDATARATE*1000

PARAM_ID = ('i', 'id')
PARAM_HOUSE = ('o', 'house')
PARAM_GROUP = ('g', 'group')
PARAM_UNIT = ('u', 'unit')
PARAM_COMMAND = ('a', 'command')
PARAM_CODE = ('c', 'code')
PARAM_DIPS = ('d', 'dips')
PARAM_DATA = ('t', 'data')

CLASS_RCSWITCH = "switch"
CLASS_RCWEATHER = "weather"

class RcCodec:
	def __init__(self):
		self.__lastDecodeParams = {}
		self.__lastDecodeTime = 0
		self._repetitions = 4

	def _decodeSymbols(self, pulseBuf):
		pbi = 0
		if hasattr(self, "_header"):
			pbi = len(self._header)

		pbmax = len(pulseBuf)
		if hasattr(self, "_footer"):
			pbmax -= len(self._footer)


		timebase = self._timebase
		if hasattr(self, "_autoTimebase"):
			asym = self._symbols[next(iter(self._symbols))]
			pulsesPerSymbol = len(asym)
			symdur = 0
			for d in asym:
				symdur += d
			numPulses = pulsesPerSymbol * self._autoTimebase[0]
			dur = self._autoTimebase[0] * symdur

			pulseSum = 0
			for pulse in pulseBuf[pbi:pbi+numPulses]:
				pulseSum += pulse
			timebase = round(pulseSum * PULSEWIDTHUS / dur)
			if (timebase < self._autoTimebase[1]) or (timebase > self._autoTimebase[2]):
				return # timebase out of range

		symbuf = ""
		symbolswindows = {}
		for key, sympulses in self._symbols.items():
			symbolswindows[key] = []
			# calculate matching windows in units of receiver's samplingtime
			for p in sympulses:
				symbolswindows[key].append((
					round(((timebase * p * (self._rxq-1)) / self._rxq) / PULSEWIDTHUS),
					round(((timebase * p * (self._rxq+1)) / self._rxq) / PULSEWIDTHUS)
				))

		while pbi < pbmax:
			symfound = False
			for symkey, windows in symbolswindows.items():
				#print("Matching symbol", symkey, windows)
				if pbmax - pbi < len(windows):
					continue # not enough pulses left in pulseBuf for current symbol. Check for next symbol

				match = True
				for idx, win in enumerate(windows):
					if (pulseBuf[pbi + idx] < win[0]) or (pulseBuf[pbi + idx] > win[1]):
						match = False
						break

				if match:
					symfound = True
					symbuf += symkey
					pbi += len(windows)
					break

			if not symfound:
				return

		if hasattr(self, "_pattern"):
			if not re.match("^" + self._pattern + "$", symbuf):
				return

		return symbuf, timebase #return decoded symbols and (measured) timebase

	def _decodeCommand(self, symbols):
		for k in self._commands:
			if self._commands[k] == symbols:
				return k
		raise Exception("Unknown command")

	def _encodeCommand(self, command):
		for key in self._commands:
			if key.lower() == command.lower():
				return self._commands[key]
		raise Exception("Invalid command '" + str(command) + "'")

	def getMqttFromParams(self, params):
		topic = self._name

		if type(params) is dict:
			tmp = list(params.values())
		else:
			tmp = params

		for v in tmp[:-1]:
			topic += '/' + str(v).upper()
		payload = tmp[-1]
		return (topic, payload)

	def decode(self, pulseBuf):
		temp = self._decodeSymbols(pulseBuf)
		if temp is not None:
			params = self._decode(temp[0])
			repeated = False
			if params == self.__lastDecodeParams:
				if time.time() - self.__lastDecodeTime < 0.5:
					repeated = True
			else:
				self.__lastDecodeParams = params
			self.__lastDecodeTime = time.time()

			return {
				"protocol": self._name,
				"class": self._class,
				"params": params,
				"symbols": temp[0],
				"timebase": temp[1]
			}, repeated, self.getMqttFromParams(params)

	def __addPulses(self, pulses):
		for pulse in pulses:
			self.__bval ^= 1
			for i in range(pulse):
				self.__bbuf <<= 1
				self.__bbuf |= self.__bval
				self.__numbits += 1
				if self.__numbits == 8:
					self.__ookdata.append(self.__bbuf)
					self.__bbuf = 0
					self.__numbits = 0

	def encode(self, params, timebase=None, repets=None):
		if not type(params) is dict:
			if not hasattr(self, "_params"):
				return
			temp = {}
			for i in range(len(params)):
				temp[self._params[i][1]] = params[i]
			params = temp

		enc = self._encode(params)
		if isinstance(enc, tuple):
			symbols = enc[0]
			repets = enc[1]
		else:
			symbols = enc

		if symbols is not None:
			self.__numbits = 0
			self.__ookdata = bytearray()
			self.__bbuf = 0
			self.__bval = 0
			pulses = []

			if hasattr(self, "_header"):
				pulses += self._header
			for s in symbols:
				pulses += self._symbols[s]
			if hasattr(self, "_footer"):
				pulses += self._footer

			self.__addPulses(pulses)

			if (self.__numbits > 0):
				self.__bval ^= 1
				self.__addPulses([8 - self.__numbits])

			if repets is None:
				repets = self._repetitions
			if timebase is None:
				timebase = self._timebase

			print(self.__ookdata, repets, timebase)
			return self.__ookdata * repets, timebase


class Tristate(RcCodec):
	'''
	Baseclass for old intertechno, Brennenstuhl RCS 1000, ...
	'''
	def __init__(self):
		self._timebase = 300
		self._autoTimebase = (4, 200, 450) # symbols, min, max
		self._rxq = 2 # rx quality factor q, matching windows s-(s/q) <= x <= s+(s/q)
		self._footer = [1, 31]
		self._symbols = {
			'0': [1, 3, 1, 3],
			'1': [3, 1, 3, 1],
			'F': [1, 3, 3, 1],
			'X': [1, 3, 1, 1] # symbol X: (used by intertechno, used for setting all channels in all groups in one house)
		}
		self._params = [PARAM_CODE]
		self._pattern = "[01FX]{12}"
		self._name = "tristate"
		self._class = CLASS_RCSWITCH
		RcCodec.__init__(self)

	def _decodeInt(self, tristateval):
		i = 0
		while tristateval != "":
			i <<= 1
			if tristateval[-1] == "F":
				i |= 1
			tristateval = tristateval[:-1]
		return i

	def _encodeInt(self, ival, digits):
		code = ""
		for i in range(digits):
			code += "F" if (ival & 0x01) > 0 else "0"
			ival >>= 1
		return code

	def _decode(self, symbols):
		return {
			"code": symbols
		}

	def _encode(self, params):
		return params["code"].upper()

class ITTristate(Tristate):
	def __init__(self):
		Tristate.__init__(self)
		self._name = "ittristate"
		self._pattern = "[0F]{8}0F(FF|F0)"
		self._params = [PARAM_HOUSE, PARAM_GROUP, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "FF", "off": "F0"}

	def _decode(self, symbols):
		house = chr(self._decodeInt(symbols[:4]) + ord('A'))
		unit = self._decodeInt(symbols[4:6]) + 1
		group = self._decodeInt(symbols[6:8]) + 1
		command = self._decodeCommand(symbols[10:12])
		return {
			"house": house,
			"group": group,
			"unit": unit,
			"command": command
		}

	def _encode(self, params):
		symbols = ""
		house = params["house"].upper()[0]
		symbols += self._encodeInt(ord(house) - ord('A'), 4)
		symbols += self._encodeInt(int(params["unit"]) - 1, 2)
		symbols += self._encodeInt(int(params["group"]) - 1, 2)
		symbols += "0F"
		symbols += self._encodeCommand(params["command"])
		return symbols


class BrennenstuhlRCS1000(Tristate):
	def __init__(self):
		Tristate.__init__(self)
		self._name = "rcs1000"
		self._pattern = "[0F]{5}(0FFF|F0FF|FF0F|FFF0)F(0F|F0)"
		self._params = [PARAM_DIPS, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "0F", "off": "F0"}

	def _decode(self, symbols):
		dips = ""
		for s in symbols[0:5]:
			dips += "1" if s == '0' else "0"
		unit = 0
		for u in symbols[5:9]:
			unit += 1
			if u == '0':
				break

		return {
			"dips": dips,
			"unit": unit,
			"command": self._decodeCommand(symbols[10:12].upper())
		}

	def _encode(self, params):
		symbols = ""
		for c in params["dips"]:
			symbols += '0' if c == '1' else 'F'
		for i in range(4):
			symbols += '0' if (int(params["unit"]) - 1) == i else 'F'
		symbols += "F"
		symbols += self._encodeCommand(params["command"])
		return symbols



class PPM32(RcCodec):
	def __init__(self):
		self._name = "intertechno"
		self._timebase = 275
		self._autoTimebase = (24, 225, 350) # symbols, min, max
		self._numsymbols = 32 # numSymbols; dimmers may have for symbols
		self._rxq = 3 # rx quality factor q, matching windows s-(s/q) <= x <= s+(s/q)
		self._header = [1, 60]
		self._footer = [1, 39]
		self._symbols = {
			'0': [1, 1, 1, 5],
			'1': [1, 5, 1, 1]
		}
		self._pattern = "[01]{32}"
		self._class = CLASS_RCSWITCH
		RcCodec.__init__(self)

class Intertechno(PPM32):
	def __init__(self):
		PPM32.__init__(self)
		self._name = "intertechno"
		self._params = [PARAM_ID, PARAM_UNIT, PARAM_COMMAND]
		self._symbols['X'] = [1, 1, 1, 1]
		self._pattern = "([01]{32})|([01]{27}X[01]{8})"
		self._commands = {"on": "1", "off": "0"}

	def _decodeUnit(self, symbols):
		return int(symbols, 2) + 1

	def _decode(self, symbols):
		id = int(symbols[:26], 2)
		unit = self._decodeUnit(symbols[28:32])
		if symbols[27] == 'X': #dimmer command
			command = int(round(int(symbols[32:36], 2) * 100 / 15.0))
		else:
			command = self._decodeCommand(symbols[27])

		return {
			"id": id,
			"unit": unit,
			"command": command
		}

	def _encodeUnit(self, unit):
		return "{:04b}".format(int(unit) - 1)

	def _encode(self, params):
		symbols = ""
		symbols += "{:026b}".format(int(params["id"]))
		symbols += "0" #group
		dim = None
		try:
			dim = int(params["command"])
			symbols += "X"
		except:
			symbols += self._encodeCommand(params["command"])

		symbols += self._encodeUnit(params["unit"])

		if dim:
			dim = int(round(15*dim/100.0))
			if dim > 15:
				dim = 15
			symbols += "{:04b}".format(dim)

		return symbols


class Hama(Intertechno):
	def __init__(self):
		Intertechno.__init__(self)
		self._name = "hama"
		self._timebase = 250
		self._timebaserange = (200, 300)

	def _decodeUnit(self, symbols):
		return 16 - int(symbols, 2)

	def _encodeUnit(self, unit):
		return "{:04b}".format(16 - int(unit))


class PWM24(RcCodec):
	'''
	Pulse Width Modulation 24 bit, chip EV1527
	Wide pulse -> 1, small pulse -> 0
	Frame: header, payload, footer
	Used by Emylo, Logilight, ...
	'''
	def __init__(self):
		RcCodec.__init__(self)
		self._timebase = 250
		self._autoTimebase = (24, 150, 400) # symbols, min, max
		self._rxq = 2 # rx quality factor q, matching windows s-(s/q) <= x <= s+(s/q)
		self._repetitions = 6
		self._pattern = "[01]{24}"
		self._symbols = {
			'1': [3, 1],
			'0': [1, 3]
		}
		self._footer = [1, 31]
		self._class = CLASS_RCSWITCH
		self._params = [PARAM_ID, PARAM_DATA]
		self._name = "EV1527"

	def _decodeBinLSB(self, symbols):
		temp = symbols[::-1] # reverse string
		return int(temp, 2)

	def _encodeBinLsb(self, val, width):
		temp = F"{val:0{width}b}"
		return temp[::-1]

	def _decode(self, symbols):
		return {
			"id": self._decodeBinLSB(symbols[:20]),
			"data": self._decodeBinLSB(symbols[20:24])
		}

	def _encode(self, params):
		symbols = ""
		symbols += self._encodeBinLsb(int(params["id"]), 20)
		symbols += self._encodeBinLsb(int(params["data"]), 4)
		return symbols

class Logilight(PWM24):
	def __init__(self):
		PWM24.__init__(self)
		self._name = "logilight"
		self._timebase = 300
		self._autoTimebase = (24, 250, 350) # symbols, min, max
		self._params = [PARAM_ID, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "1", "learn": "1", "off": "0"}

	def _decode(self, symbols):
		id = int(symbols[:20], 2)
		unit = (self._decodeBinLSB(symbols[21:24]) ^ 0x07) + 1
		command = self._decodeCommand(symbols[20])
		return {
			"id": id,
			"unit": unit,
			"command": command
		}

	def _encode(self, params):
		symbols = ""
		symbols += "{:020b}".format(int(params["id"]))
		symbols += self._encodeCommand(params["command"])
		symbols += self._encodeBinLsb((int(params["unit"]) - 1) ^ 0x07, 3)
		if (params["command"].lower() == "learn"):
			return symbols, 10
		return symbols

class Emylo(PWM24):
	def __init__(self):
		PWM24.__init__(self)
		self._name = "emylo"
		self._params = [PARAM_ID, PARAM_COMMAND]
		self._commands = {'A': '0001', 'B': '0010', 'C': '0100', 'D': '1000'}

	def _decode(self, symbols):
		id = int(symbols[:20], 2)
		command = self._decodeCommand(symbols[-4:])
		return {
			"id": id,
			"command": command
		}

	def _encode(self, params):
		symbols = ""
		symbols += "{:020b}".format(int(params["id"]))
		symbols += self._encode_command(params["command"])
		return symbols


class PilotaCasa(RcCodec):
	'''
	Pulse Width Modulation 32 bit
	Wide pulse -> 0, small pulse -> 1
	'''
	__codes = {
		'110001': (1, 1, 'on'), '111110': (1, 1, 'off'),
		'011001': (1, 2, 'on'), '010001': (1, 2, 'off'),
		'101001': (1, 3, 'on'), '100001': (1, 3, 'off'),
		'111010': (2, 1, 'on'), '110010': (2, 1, 'off'),
		'010110': (2, 2, 'on'), '011010': (2, 2, 'off'),
		'100110': (2, 3, 'on'), '101010': (2, 3, 'off'),
		'110111': (3, 1, 'on'), '111011': (3, 1, 'off'),
		'011111': (3, 2, 'on'), '010111': (3, 2, 'off'),
		'101111': (3, 3, 'on'), '100111': (3, 3, 'off'),
		'111101': (4, 1, 'on'), '110101': (4, 1, 'off'),
		'010011': (4, 2, 'on'), '011101': (4, 2, 'off'),
		'100011': (4, 3, 'on'), '101101': (4, 3, 'off'),
		'101100': (-1, -1 , 'allon'), '011100': (-1, -1, 'alloff')
	}

	def __init__(self):
		RcCodec.__init__(self)
		self._name = "pilota"
		self._timebase = 550
		self._autoTimebase = (32, 450, 650) # symbols, min, max
		self._rxq = 3 # rx quality factor q, matching windows s-(s/q) <= x <= s+(s/q)
		self._repetitions = 5
		self._pattern = "[01]{32}"
		self._symbols = {
			'1': [1, 2],
			'0': [2, 1],
		}
		self._footer = [1, 12]
		self._params = [PARAM_ID, PARAM_GROUP, PARAM_UNIT, PARAM_COMMAND]
		self._class = CLASS_RCSWITCH

	def _decode(self, symbols):
		if symbols[2:8] in self.__codes:
			c = self.__codes[symbols[2:8]]
			id = int(symbols[8:24][::-1], 2)
			return {
				"id": id, 
				"group": c[0],
				"unit": c[1],
				"command": c[2]
			}

	def _encode(self, params):
		symbols = '01'
		u = None
		cmd = params["command"].lower()
		if cmd == "learn":
			repetitions = 20
			cmd = "on"
		elif cmd in ["allon", "alloff"]:
			params["unit"] = -1
			params["group"] = -1
		for k, v in self.__codes.items():
			if v[0] == int(params["group"]) and v[1] == int(params["unit"]) and v[2] == cmd:
				u = k
				break
		symbols += u
		symbols += "{:016b}".format(int(params["id"]))[::-1]
		symbols += "11111111"
		return symbols


class Unknown(RcCodec):
	def __init__(self):
		self._timebase = 450
		self._timebaserange = (300, 400)
		self._numsymbols = 12
		self._rxq = 2 # rx quality factor q, matching windows s-(s/q) <= x <= s+(s/q)
		self._footer = [1, 31]
		self._symbols = {
			'0': [1, 3],
			'1': [3, 1],
		}
		#self._pattern = "[01FX]{12}"
		self._name = "unknown"
		self._class = CLASS_RCSWITCH
		RcCodec.__init__(self)

	def _decode(self, symbols):
		return {
			"code": symbols
		}

'''
class RcRaw(RcPulse):
	def __init__(self, timebase):
		self._timebase = timebase
		self._symbols = {}
		RcPulse.__init__(self)

	def build_raw(self, pulsetrain, repetitions):
		self._reset()
		for p in pulsetrain:
			self._add_pulses([round(p / self._timebase)])
		self._add_finish()
		return self._ookdata * repetitions


class FS20(RcPulse):
	def __init__(self):
		self._name = "fs20"
		self._timebase = 200
		self._repetitions = 6
		self._pattern = "0000000000001[01]{45}"
		self._symbols = {
			'0': [2, 2],
			'1': [3, 3],
		}
		self._header = [2, 2] * 12 + [3, 3]
		self._footer = [1, 100]
		self._params = [PARAM_ID, PARAM_UNIT, PARAM_COMMAND]
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

	def __encode_byte(self, b):
		b &= 0xFF
		result = '{:08b}'.format(b)
		par = 0
		while b:
			par ^= 1
			b &= b-1
		result += '1' if par != 0 else '0'
		return result

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		id = int(params["id"])
		unit = int(params["unit"]) - 1
		command = int(params["command"])
		symbols += self.__encode_byte((id >> 8))
		symbols += self.__encode_byte(id)
		symbols += self.__encode_byte(unit)
		symbols += self.__encode_byte(command)
		q = 0x06 + (id >> 8) + (id & 0xFF) + unit + command
		symbols += self.__encode_byte(q)
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			id = int(symbols[13:21] + symbols[22:30], 2)
			unit = int(symbols[31:39], 2) + 1
			command = int(symbols[40:48], 2)
			return [id, unit, command], tb, rep

class Voltcraft(RcPulse):

	PPM: Pulse Position Modulation
	Pulse in middle of a symbol: 0, end of symbol: 1
	Used by Voltcraft RC30
	def __init__(self):
		self._name = "voltcraft"
		self._timebase = 600
		self._repetitions = 4
		self._pattern = "[01]{20}"
		self._symbols = {
			'0': [1, 2],
			'1': [2, 1],
		}
		self._header = [1]
		self._footer = [132]
		self._params = [PARAM_ID, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"off": "000", "alloff": "100", "on": "010", "allon": "110", "dimup": "101", "dimdown": "111"}
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

	def encode(self, params, timebase=None, repetitions=None):
		if params["command"].lower() in ["on", "off"]:
			unit = int(params["unit"])-1
		else:
			unit = 3

		symbols = "{:012b}".format(int(params["id"]))[::-1]
		symbols += "{:02b}".format(unit)[::-1]
		symbols += self._encode_command(params["command"])
		symbols += "0"
		symbols += "1" if (symbols[12] == "1") ^ (symbols[14] == "1") ^ (symbols[16] == "1") else "0"
		symbols += "1" if (symbols[13] == "1") ^ (symbols[15] == "1") ^ (symbols[17] == "1") else "0"
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[1:-1])
		if symbols:
			id = int(symbols[0:12][::-1], 2)
			unit = int(symbols[12:14][::-1], 2) + 1
			command = self._decode_command(symbols[14:17])
			return [id, unit, command], tb, rep

class PilotaCasa(RcPulse):
	Pulse Width Modulation 32 bit
	Wide pulse -> 0, small pulse -> 1
	__codes = {
		'110001': (1, 1, 'on'), '111110': (1, 1, 'off'),
		'011001': (1, 2, 'on'), '010001': (1, 2, 'off'),
		'101001': (1, 3, 'on'), '100001': (1, 3, 'off'),
		'111010': (2, 1, 'on'), '110010': (2, 1, 'off'),
		'010110': (2, 2, 'on'), '011010': (2, 2, 'off'),
		'100110': (2, 3, 'on'), '101010': (2, 3, 'off'),
		'110111': (3, 1, 'on'), '111011': (3, 1, 'off'),
		'011111': (3, 2, 'on'), '010111': (3, 2, 'off'),
		'101111': (3, 3, 'on'), '100111': (3, 3, 'off'),
		'111101': (4, 1, 'on'), '110101': (4, 1, 'off'),
		'010011': (4, 2, 'on'), '011101': (4, 2, 'off'),
		'100011': (4, 3, 'on'), '101101': (4, 3, 'off'),
		'101100': (-1, -1 , 'allon'), '011100': (-1, -1, 'alloff')
	}

	def __init__(self):
		self._name = "pilota"
		self._timebase = 550
		self._repetitions = 5
		self._pattern = "[01]{32}"
		self._symbols = {
			'1': [1, 2],
			'0': [2, 1],
		}
		self._footer = [1, 12]
		self._params = [PARAM_ID, PARAM_GROUP, PARAM_UNIT, PARAM_COMMAND]
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

	def encode(self, params, timebase=None, repetitions=None):
		symbols = '01'
		u = None
		cmd = params["command"].lower()
		if cmd == "learn":
			repetitions = 20
			cmd = "on"
		elif cmd in ["allon", "alloff"]:
			params["unit"] = -1
			params["group"] = -1
		for k, v in self.__codes.items():
			if v[0] == int(params["group"]) and v[1] == int(params["unit"]) and v[2] == cmd:
				u = k
				break
		symbols += u
		symbols += "{:016b}".format(int(params["id"]))[::-1]
		symbols += "11111111"
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[:-2])
		if symbols and (symbols[2:8] in self.__codes):
			c = self.__codes[symbols[2:8]]
			id = int(symbols[8:24][::-1], 2)
			return [id, c[0], c[1], c[2]], tb, rep

			
class PCPIR(TristateBase): #pilota casa PIR sensor
	# Pilota Casa IR sensor

	def __init__(self):
		self._name = "pcpir"
		self._params = [PARAM_ID, PARAM_COMMAND]
		self._timebase = 500
		self._commands = {"off": "0", "on": "F"}
		TristateBase.__init__(self)

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			id = self._decode_int(symbols[5:10])
			unit = self._decode_int(symbols[0:5])
			command = self._decode_command(symbols[11:12])
			return [id, unit, command], tb, rep


class REVRitterShutter(RcPulse):
	Pulse Width Modulation 24 bit, 
	Short pulse: 0, long pulse: 1
	Used by REV Ritter shutter contact SA-MC08-N04-D
	def __init__(self):
		self._name = "revshutter"
		self._timebase = 200
		self._repetitions = 4
		self._pattern = "[01]{24}"
		self._symbols = {
			'0': [1, 3],
			'1': [3, 1],
		}
		self._footer = [1, 85]
		self._params = [PARAM_ID]
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

	def encode(self, params, timebase=None, repetitions=None):
		symbols = "{:024b}".format(int(params["id"]))
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			id = int(symbols[0:24], 2)
			return [id], tb, rep

class WH2(RcPulse):
	Temperature & humidity sensor WH2, Telldus
	Pulse Duration Modulation
	Short, middle = 1, long middle = 0
	def __init__(self):
		self._name = "wh2"
		self._class = CLASS_RCWEATHER
		self._timebase = 500
		self._pattern = "11111111[01]{39}"
		self._symbols = {
			'1': [1, 2],
			'0': [3, 2],
		}
		self._footer = [2, 49]
		RcPulse.__init__(self)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			symbols += "0"

			id = "{:02x}".format(int(symbols[12:20], 2))
			T = int(symbols[20:32], 2)
			if T >= 1<<11:
				T -= 1<<12
			T /= 10.0

			res = [id, T]
			RH = int(symbols[32:40], 2)
			if RH != 0xFF:
				res.append(RH)

			return res, tb, rep

	def get_decode_dict(self, decresult):
		res = {
			"id": decresult[0],
			"T": decresult[1]
		}
		if len(decresult) >= 3:
			res["RH"] = decresult[2]

		return res

	def get_mqtt_from_dict(self, di):
		topic = "/" + di["id"]
		msg = {
			"T": di["T"]
		}
		if "RH" in di:
			msg["RH"] = di["RH"]
		return topic, json.dumps(msg)


class WS7000(RcPulse):
	Temperature & humidity sensor LaCrosee/ELV
	Pulse Width Modulation
	Short = 1, long = 2
	def __init__(self):
		self._name = "ws7000"
		self._class = CLASS_RCWEATHER
		self._timebase = 400
		self._pattern = "^0{5,}1([01]{4}1){6,}[01]{4,5}$"
		self._symbols = {
			'1': [1, 2],
			'0': [2, 1],
		}
		self._footer = [2, 49]
		RcPulse.__init__(self)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			symbols = symbols[symbols.find("000001") + 6:]
			n = [] #nibbles
			i = 0
			check = 0
			while i <= len(symbols) - 4:
				n.append(int(symbols[i:i+4][::-1], 2))
				i += 5
				if i <= len(symbols) - 4:
					check ^= n[-1]
			if check != 0:
				return

			res = {}
			res["id"] = (n[0] << 4) | (n[1] & 0x07)

			if n[0] == 1: #WS7000 has subtypes
				#WS7000-22/25
				t = n[2] * 0.1 + n[3] * 1 + n[4] * 10
				if (n[1] & 0x8) == 0x8:
					t = -t
				res["T"] = t
				res["unit"] = n[1] & 0x7
				h = n[5] * 0.1 + n[6] * 1 + n[7] * 10
				if h > 0:
					res["RH"] = h
				return res, tb, rep

class TX141TH(RcPulse):
	Temperature & humidity sensor LaCrosse TX141TH / TFA Dostmann 30.3221.02
	Pulse Width Modulation
	def __init__(self):
		self._name = "TX141TH"
		self._class = CLASS_RCWEATHER
		self._timebase = 250
		self._pattern = "^[01]{40}$"
		self._symbols = {
			'0': [1, 2],
			'1': [2, 1]
		}
		RcPulse.__init__(self)

	def check_crc(self, symbols):
		a = []
		sum = 0
		key = 0xf4
		for i in range(0, 32, 8):
			b = int(symbols[24-i:32-i], 2)
			for j in range(8):
				if ((b >> j) & 1) != 0:
					sum ^= key

				if (key & 0x80) != 0:
					key = (key << 1) ^ 0x31
				else:
					key = key << 1

		return (sum & 0xff) == int(symbols[32:40], 2)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[8:88])
		if symbols:
			if self.check_crc(symbols):
				res = {}
				id = int(symbols[0:8], 2)
				ch = int(symbols[10:12], 2) + 1
				T = (int(symbols[12:24], 2) - 500) / 10
				RH = int(symbols[24:32], 2)
				return [id, ch, T, RH], tb, rep

	def get_decode_dict(self, decresult):
		res = {
			"id": decresult[0],
			"ch": decresult[1],
			"T": decresult[2],
			"RH": decresult[3]
		}
		return res

	def get_mqtt_from_dict(self, di):
		topic = "/" + str(di["id"]) + "/" + str(di["ch"])
		msg = {
			"T": di["T"],
			"RH": di["RH"]
		}
		return topic, json.dumps(msg)

class TFA30_3120_90(RcPulse):
	Temperature & humidity sensor TFA 30.3120.90
	Pulse Width Modulation
	def __init__(self):
		self._name = "TFA_30_3120_90"
		self._class = CLASS_RCWEATHER
		self._timebase = 250
		self._pattern = "^[01]{44}$"
		self._symbols = {
			'0': [5, 4],
			'1': [2, 4]
		}
		RcPulse.__init__(self)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:87] + [1000])
		if symbols:
			chk = 0
			for i in range(0, 40, 4):
				chk += int(symbols[i:i+4], 2)
			if (chk & 0x0F) != int(symbols[40:44], 2):
				return
			id = int(symbols[12:19], 2)
			msgtype = int(symbols[8:12], 2)

			if msgtype == 0x00:
				T = int(symbols[20:24], 2) * 10 + int(symbols[24:28], 2) + int(symbols[28:32], 2) / 10 - 50
				return [id, T], tb, rep
			elif msgtype == 0x0E:
				pass

	def get_decode_dict(self, decresult):
		res = {
			"id": decresult[0],
			"T": decresult[1]
		}
		return res

	def get_mqtt_from_dict(self, di):
		topic = "/" + str(di["id"])
		msg = {
			"T": di["T"]
		}
		return topic, json.dumps(msg)

'''

protocols = [
	Intertechno(),
	Tristate(),
	ITTristate(),
	BrennenstuhlRCS1000(),
	Hama(),
	Logilight(),
	Emylo(),
	PilotaCasa(),
	PWM24()

	#Voltcraft(),
	#PCPIR(),
	#FS20(),
	#REVRitterShutter(),
	#WH2(),
	#WS7000(),
	#TX141TH(),
	#TFA30_3120_90()
]

def get_protocol(name):
	for p in protocols:
		if p._name == name:
			return p
	return None

class RfmPulseTRX(threading.Thread):
	def __init__(self, module, rxcb, frequency):
		self.__rfm = RaspyRFM(module, RFM69)
		self.__rfm.set_params(
			Freq = frequency, # MHz
			Bandwidth = 500, # kHz
			SyncPattern = [],
			RssiThresh = -70, # dBm
			ModulationType = rfm69.OOK,
			OokThreshType = 1, # peak thresh
			OokPeakThreshDec = 3, # decrement once every 8 chips
			OokFixedThresh = 125, # floor threshold in peak mode
			Preamble = 0,
			TxPower = 13
		)
		self.__rxevent = threading.Event()
		self.__rxevent.set()
		self.__rfmlock = threading.Lock()

		if rxcb is not None:
			self.__rxtraincb = rxcb
			threading.Thread.__init__(self)
			self.daemon = True
			self.start()

	def run(self):
		while True:
			self.__rxevent.wait()
			self.__rfmlock.acquire()
			self.__rfm.set_params(Datarate = RXDATARATE)
			self.__rfm.receive_start(0) # unlimited length
			self.__receive()
			self.__rfm.receive_end()
			self.__rfmlock.release()
			continue

	def __receive(self):
		bit = False
		pulseLen = 1
		pulseBuf = collections.deque(maxlen=200)
		preFlag = False
		while True:
			fifo = self.__rfm.read_fifo_wait(64)
			if len(fifo) == 0:
				return

			for b in fifo:
				mask = 0x80
				while mask != 0:
					newbit = (b & mask) != 0

					if newbit != bit:
						if not preFlag:
							pulseBuf.append(pulseLen)
						preFlag = False
						pulseLen = 1
						bit = newbit
					else:
						pulseLen += 1
						if pulseLen == 120:
							pulseBuf.append(pulseLen)
							self.__rxtraincb(pulseBuf)
							pulseBuf.clear()
							preFlag = True

					mask >>= 1

	def send(self, train, timebase):
		self.__rxevent.clear()
		self.__rfm.receive_stop()
		self.__rfmlock.acquire()
		self.__rfm.set_params(
			Datarate = 1000.0 / timebase
		)
		self.__rfm.send(train)
		self.__rfmlock.release()
		self.__rxevent.set()

class RcTransceiver(threading.Thread):
	def __init__(self, module, frequency, rxcallback, statecallback = None):
		threading.Thread.__init__(self)
		self.__lock = threading.Lock()
		self.__event = threading.Event()
		self.__trainbuf = []
		self.daemon = True
		cb = None if rxcallback is None else self.__pushPulseTrain
		if cb is not None:
			self.start()
		self.__rxcb = rxcallback
		self.__statecb = statecallback
		self.__rfmtrx = RfmPulseTRX(module, cb, frequency)

	def __del__(self):
		del self.__rfmtrx

	def __pushPulseTrain(self, train):
		if len(train) < 20:
			return
		self.__lock.acquire()
		self.__trainbuf.append(list(train))
		self.__event.set()
		self.__lock.release()

	def __decode(self, train):
		res = []
		succ = False
		for p in protocols:
			try:
				decres = p.decode(train)
				if decres is None:
					continue
				data = decres[0]
				repeated = decres[1]
				mqtt = decres[2]

				succ = True
				if not repeated:
					res.append(data)

					if self.__statecb:
						self.__statecb(mqtt[0], mqtt[1])

			except Exception as e:
				#print(e)
				pass

		self.__rxcb(res if succ else None, train)

	def send(self, protocol, params, timebase=None, repeats=None):
		proto = get_protocol(protocol)
		if proto:
			try:
				txdata, tb = proto.encode(params, timebase, repeats)
				print(txdata, tb)
				self.__rfmtrx.send(txdata, tb)
				if self.__statecb:
					topic, msg = proto.getMqttFromParams(params)
					self.__statecb(topic, msg)
			except Exception as e:
				raise(e)
				print("Encode error: " + str(e))

	def run(self):
		while True:
			self.__event.wait()
			self.__lock.acquire()
			train = None
			if len(self.__trainbuf) > 0:
				train = self.__trainbuf.pop()
			else:
				self.__event.clear()
			self.__lock.release()
			if (train != None):
				self.__decode(train)

