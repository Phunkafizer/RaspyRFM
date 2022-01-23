import re
from argparse import ArgumentParser
from raspyrfm import *
import threading
import time
import json

PARAM_ID = ('i', 'id')
PARAM_HOUSE = ('o', 'house')
PARAM_GROUP = ('g', 'group')
PARAM_UNIT = ('u', 'unit')
PARAM_COMMAND = ('a', 'command')
PARAM_CODE = ('c', 'code')
PARAM_DIPS = ('d', 'dips')

CLASS_RCSWITCH = "switch"
CLASS_RCWEATHER = "weather"

class RcPulse:
	def __init__(self):
		self.__numbits = 0
		self._ookdata = bytearray()
		self.__bbuf = 0
		self.__bval = 0
		self._parser = ArgumentParser()
		self._lastdecode = None
		self._lastdecodetime = 0

		symset = set()
		for k in self._symbols:
			symset |= set(self._symbols[k])

		symlist = list(symset)
		symlist.sort()
		q = 0
		for i in range(len(symlist) - 1):
			if 1.0 * symlist[i] / symlist[i+1] > q:
				q = 1.0 * symlist[i] / symlist[i+1]
				p1 = 1.0 * symlist[i]
				p2 = 1.0 * symlist[i+1]

		f = (p2-p1) / (p2+p1)

		self._minwidth = self._timebase * (1 - f)
		self._maxwidth = self._timebase * (1 + f)

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
				return None, None, None

		if re.match("^" + self._pattern + "$", dec):
			rep = True
			if (self._lastdecode != dec) or (time.time() - self._lastdecodetime > 0.5):
				self._lastdecode = dec
				rep = False
			self._lastdecodetime = time.time()
			return dec, int(1.0 * sumpulse / sumstep), rep

		return None, None, None

	def _encode_command(self, command):
		for key in self._commands:
			if key.lower() == command.lower():
				return self._commands[key]
		raise Exception("Invalid command '" + str(command) + "'")

	def _decode_command(self, symbols):
		for k in self._commands:
			if self._commands[k] == symbols:
				return k
		raise Exception("Unknown command")

	def _build_frame(self, symbols, timebase=None, repetitions=None):
		self._reset()

		if hasattr(self, '_header'):
			self._add_pulses(self._header)
		self._add_symbols(symbols)
		if hasattr(self, '_footer'):
			self._add_pulses(self._footer)
		self._add_finish()
		if repetitions is None:
			repetitions = self._repetitions
		return self._ookdata * repetitions, timebase if timebase else self._timebase

	def decode(self, pulsetrain):
		pass

	def encode(self, params):
		pass

	def get_decode_dict(self, decresult):
		if not hasattr(self, "_params"):
			return None
		result = {}
		for i in range(len(decresult)):
			result[self._params[i][1]] = decresult[i]
		return result

	def get_mqtt_from_dict(self, li):
		topic = ""
		for i in range(len(self._params[:-1])):
			topic += "/" + str(li[self._params[i][1]])
		return topic, li[self._params[-1][1]].upper()


class TristateBase(RcPulse): #Baseclass for old intertechno, Brennenstuhl, ...
	def __init__(self):
		if not hasattr(self, "_timebase"):
			self._timebase = 300
		self._repetitions = 4
		self._pattern = "[01F]{12}"
		self._symbols = { 
			'0': [1, 3, 1, 3],
			'1': [3, 1, 3, 1],
			'F': [1, 3, 3, 1],
		}
		self._footer = [1, 31]
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

	def _encode_int(self, ival, digits):
		code = ""
		for i in range(digits):
			code += "F" if (ival & 0x01) > 0 else "0"
			ival >>= 1
		return code

	def _decode_int(self, tristateval):
		i = 0
		while tristateval != "":
			i <<= 1
			if tristateval[-1] == "F":
				i |= 1
			tristateval = tristateval[:-1]
		return i


class Tristate(TristateBase):
	def __init__(self):
		self._name = "tristate"
		TristateBase.__init__(self)
		self._params = [PARAM_CODE]

	def encode(self, params, timebase=None, repetitions=None):
		return self._build_frame(params["code"].upper(), timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			return {"code": symbols}, tb, rep, [], symbols

class ITTristate(TristateBase): #old intertechno
	def __init__(self):
		self._name = "ittristate"
		TristateBase.__init__(self)
		self._pattern = "[0F]{8}0F(FF|F0)"
		self._params = [PARAM_HOUSE, PARAM_GROUP, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "FF", "off": "F0"}

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		house = params["house"].upper()[0]
		symbols += self._encode_int(ord(house) - ord('A'), 4)
		symbols += self._encode_int(int(params["unit"]) - 1, 2)
		symbols += self._encode_int(int(params["group"]) - 1, 2)
		symbols += "0F"
		symbols += self._encode_command(params["command"])
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			house = chr(self._decode_int(symbols[:4]) + ord('A'))
			unit = self._decode_int(symbols[4:6]) + 1
			group = self._decode_int(symbols[6:8]) + 1
			command = self._decode_command(symbols[10:12])
			return [house, group, unit, command], tb, rep

class Brennenstuhl(TristateBase):
	def __init__(self):
		self._name = "brennenstuhl"
		TristateBase.__init__(self)
		self._pattern = "[0F]{5}(0FFF|F0FF|FF0F|FFF0)F(0F|F0)"
		self._params = [PARAM_DIPS, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "0F", "off": "F0"}

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		for c in params["dips"]:
			symbols += '0' if c == '1' else 'F'
		for i in range(4):
			symbols += '0' if (int(params["unit"]) - 1) == i else 'F'
		symbols += "F"
		symbols += self._encode_command(params["command"])
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[0:-2])
		if symbols:
			dips = ""
			for s in symbols[0:5]:
				dips += "1" if s == '0' else "0"
			unit = 0
			for u in symbols[5:9]:
				unit += 1
				if u == '0':
					break

			command = self._decode_command(symbols[10:12].upper())
			return [dips, unit, command], tb, rep

class PPM1(RcPulse): #Intertechno, Hama, Nexa, Telldus, ...
	'''
	PDM1: Pulse Position Modulation
	Every bit consists of 2 shortpulses. Long distance between these pulses 2 pulses -> 1, else -> 0
	Frame: header, payload, footer
	Used by Intertechno self learning, Hama, ...
	'''
	def __init__(self):
		self._timebase = 250
		self._repetitions = 4
		self._pattern = "[01]{32}"
		self._header = [1, 11]
		self._symbols = {
			'0': [1, 1, 1, 5],
			'1': [1, 5, 1, 1],
		}
		self._footer = [1, 39]
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

class Intertechno(PPM1):
	def __init__(self):
		self._name = "intertechno"
		self._params = [PARAM_ID, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "1", "off": "0"}
		self._timebase = 275
		PPM1.__init__(self)

	def _encode_unit(self, unit):
		return "{:04b}".format(int(unit) - 1)

	def _decode_unit(self, unit):
		return int(unit, 2) + 1

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		symbols += "{:026b}".format(int(params["id"]))
		symbols += "0" #group
		symbols += self._encode_command(params["command"])
		symbols += self._encode_unit(params["unit"])
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[2:-2])
		if symbols:
			id = int(symbols[:26], 2)
			unit = self._decode_unit(symbols[28:32])
			command = self._decode_command(symbols[27])
			return [id, unit, command], tb, rep

class Hama(Intertechno):
	def __init__(self):
		Intertechno.__init__(self)
		self._name = "hama"
		self._timebase = 250

	def _encode_unit(self, unit):
		return "{:04b}".format(16 - int(unit))

	def _decode_unit(self, unit):
		return 16 - int(unit, 2)


class PWM1(RcPulse):
	'''
	PWM1: Pulse Width Modulation 24 bit
	Wide pulse -> 1, small pulse -> 0
	Frame: header, payload, footer
	Used by Emylo, Logilight, ...
	'''
	def __init__(self):
		self._timebase = 300
		self._repetitions = 6
		self._pattern = "[01]{24}"
		self._symbols = {
			'1': [3, 1],
			'0': [1, 3],
		}
		self._footer = [1, 31]
		self._class = CLASS_RCSWITCH
		RcPulse.__init__(self)

class Logilight(PWM1):
	def __init__(self):
		self._name = "logilight"
		self._params = [PARAM_ID, PARAM_UNIT, PARAM_COMMAND]
		self._commands = {"on": "1", "learn": "1", "off": "0"}
		PWM1.__init__(self)

	def _encode_unit(self, unit):
		res = ""
		mask = 0x01
		while mask < 0x08:
			res += '1' if ((int(unit) - 1) & mask) == 0 else '0'
			mask <<= 1
		return res

	def _decode_unit(self, unit):
		i = 0
		while unit:
			i <<= 1
			if unit[-1] == '0':
				i |= 1
			unit = unit[:-1]
		return i + 1

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		symbols += "{:020b}".format(int(params["id"]))
		symbols += self._encode_command(params["command"])
		symbols += self._encode_unit(params["unit"])
		if (params["command"].lower() == "learn"):
			repetitions = 10
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[:-2])
		if symbols:
			id = int(symbols[:20], 2)
			unit = self._decode_unit(symbols[21:24])
			command = self._decode_command(symbols[20])
			return [id, unit, command], tb, rep

class Emylo(PWM1):
	def __init__(self):
		self._name = "emylo"
		self._params = [PARAM_ID, PARAM_COMMAND]
		self._commands = {'A': '0001', 'B': '0010', 'C': '0100', 'D': '1000'}
		PWM1.__init__(self)

	def encode(self, params, timebase=None, repetitions=None):
		symbols = ""
		symbols += "{:020b}".format(int(params["id"]))
		symbols += self._encode_command(params["command"])
		return self._build_frame(symbols, timebase, repetitions)

	def decode(self, pulsetrain):
		symbols, tb, rep = self._decode_symbols(pulsetrain[:-2])
		if symbols:
			id = int(symbols[:20], 2)
			command = self._decode_command(symbols[-4:])
			return [id, command], tb, rep

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
	'''
	PPM: Pulse Position Modulation
	Pulse in middle of a symbol: 0, end of symbol: 1
	Used by Voltcraft RC30
	'''
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
	'''
	Pilota Casa IR sensor
	'''
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
	'''
	Pulse Width Modulation 24 bit, 
	Short pulse: 0, long pulse: 1
	Used by REV Ritter shutter contact SA-MC08-N04-D
	'''
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
	'''
	Temperature & humidity sensor WH2, Telldus
	Pulse Duration Modulation
	Short, middle = 1, long middle = 0
	'''
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
	'''
	Temperature & humidity sensor LaCrosee/ELV
	Pulse Width Modulation
	Short = 1, long = 2
	'''
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
				return res, tb, rep, None, None

protocols = [
	Tristate(),
	ITTristate(),
	Brennenstuhl(),
	Intertechno(),
	Hama(),
	Logilight(),
	Emylo(),
	Voltcraft(),
	PCPIR(),
	FS20(),
	PilotaCasa(),
	REVRitterShutter(),
	WH2(),
	WS7000(),
]

def get_protocol(name):
	for p in protocols:
		if p._name == name:
			return p
	return None

RXDATARATE = 20.0 #kbit/s
class RfmPulseTRX(threading.Thread):
	def __init__(self, module, rxcb, frequency):
		self.__rfm = RaspyRFM(module, RFM69)
		self.__rfm.set_params(
			Freq = frequency, #MHz
			Bandwidth = 500, #kHz
			SyncPattern = [],
			RssiThresh = -105, #dBm
			ModulationType = rfm69.OOK,
			OokThreshType = 1, #peak thresh
			OokPeakThreshDec = 3,
			Preamble = 0,
			TxPower = 13
		)
		self.__rxtraincb = rxcb
		self.__event = threading.Event()
		self.__event.set()
		threading.Thread.__init__(self)
		self.daemon = True
		self.start()

	def run(self):
		while True:
			self.__event.wait()
			self.__rfm.set_params(
				Datarate = RXDATARATE #kbit/s
			)
			self.__rfm.start_receive(self.__rxcb)

	def __rxcb(self, rfm):
		bit = False
		cnt = 1
		train = []
		bitfifo = 0
		while self.__event.isSet():
			fifo = rfm.read_fifo_wait(64)

			for b in fifo:
				mask = 0x80
				while mask != 0:
					newbit = (b & mask) != 0

					''' filter
					bitfifo <<= 1
					if newbit:
						bitfifo |= 1
					v = bitfifo & 0x3
					c = 0
					while v > 0:
						v &= v - 1
						c += 1
					'''

					if newbit == bit:
						cnt += 1
					else:
						if cnt < 150*RXDATARATE/1000: #<150 us
							train *= 0 #clear
						elif cnt > 4000*RXDATARATE/1000:
							if not bit:
								train.append(cnt)
								if len(train) > 20:
									self.__rxtraincb(train)
							train *= 0 #clear
						elif len(train) > 0 or bit:
							train.append(cnt)
						cnt = 1
						bit = not bit
					mask >>= 1

	def send(self, train, timebase):
		self.__event.clear()
		self.__rfm.set_params(
			Datarate = 1000.0 / timebase
		)
		self.__event.set()
		self.__rfm.send(train)

class RcTransceiver(threading.Thread):
	def __init__(self, module, frequency, rxcallback, statecallback = None):
		threading.Thread.__init__(self)
		self.__lock = threading.Lock()
		self.__event = threading.Event()
		self.__trainbuf = []
		self.daemon = True
		self.start()
		self.__rxcb = rxcallback
		self.__statecb = statecallback
		self.__rfmtrx = RfmPulseTRX(module, self.__pushPulseTrain, frequency)

	def __del__(self):
		del self.__rfmtrx

	def __pushPulseTrain(self, train):
		self.__lock.acquire()
		self.__trainbuf.append(list(train))
		self.__event.set()
		self.__lock.release()

	def __decode(self, train):
		res = []
		succ = False
		for p in protocols:
			try:
				dec, tb, rep = p.decode(train)
				if dec:
					succ = True
					if not rep:
						decdict = p.get_decode_dict(dec)
						resitem = {
							"protocol": p._name,
							"class": p._class,
							"params": decdict
						}
						res.append(resitem)

						if self.__statecb:
							topic, msg = p.get_mqtt_from_dict(decdict)
							topic = p._name + topic
							self.__statecb(topic, msg)

			except Exception as e:
				pass

		self.__rxcb(res if succ else None, train)

	def send(self, protocol, params, timebase=None, repeats=None):
		proto = get_protocol(protocol)
		if proto:
			try:
				if not type(params) is dict:
					params = proto.get_decode_dict(params)
				txdata, tb = proto.encode(params, timebase, repeats)
				self.__rfmtrx.send(txdata, tb)
				if self.__statecb:
					topic, msg = proto.get_mqtt_from_dict(params)
					topic = proto._name + topic
					self.__statecb(topic, msg)
			except Exception as e:
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
				for i, v in enumerate(train):
					train[i] = int(v * 1000 / RXDATARATE) #convert to microseconds
				self.__decode(train)
