import datetime
import json
import climatools

def crc8(buf):
        crc = 0
        for b in buf:
                crc = crc ^ b
                for i in range(8):
                        if (crc & 0x80 == 0x80):
                                crc = (crc << 1) ^ 0x31
                        else:
                                crc <<= 1
        return crc & 0xFF

def crc_ccitt16(datain):
    crc = 0xFFFF
    for d in datain:
        d ^= crc & 0xFF
        d = (d ^ (d << 4)) & 0xFF
        crc = ((d << 8) | (crc >> 8)) ^ (d >> 4) ^ (d << 3)
    return crc

def lfsr_digest16(data, gen, key):
    sum = 0
    for b in data:
        for i in range(7, -1, -1):
            if (b >> i) & 1 > 0:
                sum ^= key
            key = (key >> 1) ^ (gen if (key & 1) > 0 else 0)
    return sum

def csum(data):
    s = 0
    for i in data:
        s += i
    return s & 0xFF

def bcdToInt(msg, numNibbles, startOdd = False):
    if startOdd:
        bitpos = 4
        numNibbles += 1
    else:
        bitpos = 0
    result = 0
    while bitpos < numNibbles * 4:
        result *= 10
        result += msg[bitpos // 8] >> (4 - (bitpos % 8)) & 0x0F
        bitpos += 4
    return result

def getInt(data):
    result = 0
    for d in data:
        result <<= 8
        result |= d
    return result

def nibblesToInt(nibbles):
    result = 0
    for n in nibbles:
        result = (result << 4) | n
    return result

def toNibbles(data):
    result = []
    for b in data:
        result += [b >> 4, b & 0x0F]
    return result

class SensorRegistry:
    def __init__(self):
        self.__sensors = {}

    def getSensor(self, key):
        if not key in self.__sensors:
            self.__sensors[key] = {"count": (0, None)}

        result = self.__sensors[key]
        result['count'] = (result['count'][0] + 1, None)
        return result

sensorRegistry = SensorRegistry()

class BaseSensor:
    _dbFields = []
    def __init__(self, id, rssi, fei):
        self.__fields = {}
        self.__calcs = {}
        self.__tags = {}
        self._discFlag = False
        self._setTag('ID', id)
        self._setField('RSSI', rssi, 'dBm')
        self._setField('FEI', round(fei / 1000, 2), 'kHz')
        self.__cache = sensorRegistry.getSensor((self.__class__.__name__, id))

    def __str__(self):
        result = self.__class__.__name__ + ': '
        for key in self.__tags:
            result += f'{key}={self.__tags[key]}, '
        values = self.getValues()
        for key in values:
            val = values[key]
            result += f'{key}={val[0]}' + (f' {val[1]}, ' if val[1] != None else ', ')
        return result

    def getId(self):
        if 'ID' in self.__tags:
            return self.__tags['ID']

    def getType(self):
        return self.__class__.__name__

    def getClass(self):
        return self._sensorClass

    def getJSON(self):
        return json.dumps(self.getValues())

    def getValues(self):
        dict = {}
        for key in self.__fields:
            dict[key] = val = self.__fields[key]
        for key in self.__calcs:
            dict[key] = val = self.__calcs[key]
        for key in self.__cache:
            dict[key] = self.__cache[key]
        return dict

    def getDbValues(self):
        result = {}
        for f in self._dbFields:
            if f in self.__fields:
                result[f] = self.__fields[f]
            if f in self.__calcs:
                result[f] = self.__calcs[f]
        return result

    def getDiscoveryPaths(self):
        return []

    def _setField(self, symbol, val, unit=None):
        self.__fields[symbol] = (val, unit)
        if not hasattr(self, 'minMaxFieldNames'):
            return
        if symbol in self.minMaxFieldNames:
            if not symbol + '_min' in self.__cache:
                self.__cache[symbol + '_min'] = (val, unit)
            else:
                if val < self.__cache[symbol + '_min'][0]:
                    self.__cache[symbol + '_min'] = (val, unit)
            if not symbol + '_max' in self.__cache:
                self.__cache[symbol + '_max'] = (val, unit)
            else:
                if val > self.__cache[symbol + '_max'][0]:
                    self.__cache[symbol + '_max'] = (val, unit)

    def _setCalc(self, symbol, val, unit=None):
        self.__calcs[symbol] = (val, unit)

    def _setTag(self, name, val):
        self.__tags[name] = val

class WeatherSensor(BaseSensor):
    minMaxFieldNames = ['T', 'RH']
    _sensorClass = 'weather'
    _dbFields = ['T', 'RH', 'DEW', 'AH']
    def _set(self, T, RH = None):
        self._setField('T', T, '°C')
        if RH:
            self._setField('RH', RH, '%')
            self._setCalc('AH', round(climatools.calcAH(T, RH), 1), 'g/m³')
            self._setCalc('SVP', round(climatools.calcSVP(T), 1), 'hPa')
            self._setCalc('VP', round(climatools.calcVP(T, RH), 1), 'hPa')
            self._setCalc('DEW', climatools.calcDewPoint(T, RH), '°C')
            self._setCalc('TH80', climatools.calcDewPoint(T, RH, False, 80), '°C')
            self._setCalc('TH60', climatools.calcDewPoint(T, RH, False, 60), '°C')

    def getDiscoveryPaths(self):
        result = []
        for fk in self.__fields:
            pass


class EnergySensor(BaseSensor):
    _sensorClass = 'energy'
    _dbFields = ['P', 'U', 'I']
    def _set(self, P, U, I, E):
        if not P is None:
            self._setField('P', P, 'W')
        if not U is None:
            self._setField('U', U, 'V')
        if not I is None:
            self._setField('I', I, 'A')
        if not E is None:
            self._setField('E', E, 'kWh')

class LaCrosseIT(WeatherSensor):
    def __init__(self, nibbles, rssi, fei):
        id = nibblesToInt(nibbles[1:3]) & 0xFC#
        BaseSensor.__init__(self, f'{id:x}', rssi, fei)
        T = 10 * (nibbles[3] - 4) + nibbles[4] + nibbles[5] / 10.0

        rh = nibblesToInt(nibbles[6:8]) & 0x7F
        if (rh < 0) or (rh > 100):
            rh = None

        self._set(T, rh)
        self._setField('init', nibbles[2] & 0x2 != 0)
        self._setField('batlo', nibbles[6] & 0x8 != 0)

    @staticmethod
    def decode(msg, rssi, fei):
        if len(msg) < 5:
            return
        if crc8(msg[0:5]) != 0:
            return
        nibbles = toNibbles(msg)
        if nibbles[0] != 9:
            return
        if (msg[1] & 0x0F > 9) or (msg[2] >> 4 > 9) or (msg[2] & 0x0F > 9):
            return

        return LaCrosseIT(nibbles, rssi, fei)

class EMT7110(EnergySensor):
    def __init__(self, msg, rssi, fei):
        id = getInt(msg[0:4])
        BaseSensor.__init__(self, f'{id:8x}', rssi, fei)
        P = (getInt(msg[4:6]) & 0x3FFF) / 2
        U = msg[8] / 2 + 128
        I = getInt(msg[6:8]) / 1000
        E = (getInt(msg[9:11]) & 0x3FFF) / 100
        self._set(P, U, I, E)

    @staticmethod
    def decode(msg, rssi, fei):
        if len(msg) < 12:
            return
        cs = csum(msg[0:12])
        if cs != 0:
            return
        return EMT7110(msg, rssi, fei)

class Bresser7in1(WeatherSensor):
    _dbFields = WeatherSensor._dbFields + ['Ev', 'Vavg', 'UVidx']
    def __init__(self, msg, rssi, fei):
        id = f'{getInt(msg[2:4])}'
        BaseSensor.__init__(self, id, rssi, fei)

        temp_raw = bcdToInt(msg[14:16], 3)
        temp_c = temp_raw * 0.1;
        if temp_raw > 600:
            temp_c = (temp_raw - 1000) / 10
        self._set(round(temp_c, 1), bcdToInt(msg[16:17], 2))
        self._setField('Ev', bcdToInt(msg[17:20], 6), 'lx')
        self._setField('rain', bcdToInt(msg[10:13], 6) / 10, 'mm')
        self._setField('Vgust', bcdToInt(msg[7:9], 3) / 10, 'm/s')
        self._setField('Vavg', bcdToInt(msg[8:10], 3, True) / 10, 'm/s')
        self._setField('wDir', bcdToInt(msg[4:6], 3), '°')
        self._setField('UVidx', bcdToInt(msg[20:22], 3) / 10)
        flags = msg[15] & 0x0f
        self._setField('batlo', flags & 0x06 == 0x06)

    @staticmethod
    def decode(msg, rssi, fei):
        if len(msg) < 25:
            return

        for i in range(len(msg)):
            msg[i] = msg[i] ^ 0xAA

        dig = lfsr_digest16(msg[2:25], 0x8810, 0xba95)
        msgdig = (msg[0] << 8) | msg[1]
        if msgdig ^ dig != 0x6df1:
            return

        return Bresser7in1(msg, rssi, fei)

class EC3000(BaseSensor):
    def __init__(self, nibbles, rssi, fei):
        id = f'{nibblesToInt(nibbles[1:5])}'
        BaseSensor.__init__(self, id, rssi, fei)

        p = nibblesToInt(nibbles[31:35]) / 10
        self._setField('P', p, 'W')

        pmax = nibblesToInt(nibbles[35:39]) / 10
        self._setField('Pmax', pmax, 'W')

        e = nibblesToInt(nibbles[67:71] + nibbles[24:31])
        self._setField('E', e / 3600 / 1000, 'kWh')

        flags = nibblesToInt(nibbles[76:77])
        self._setField('onState', flags & 0x08 != 0)

    @staticmethod
    def __count1bits(value):
        c = 0
        while (value > 0):
            c += 1
            value &= value - 1
        return c

    @staticmethod
    def __descramble(datain):
        dataout = []
        lfsr = 0xF185D3AC
        outbyte = 0
        for b in datain:
            inb = b
            for bit in range(8):
                inbit = (inb & 0x80) >> 7
                outbit = inbit ^ (EC3000.__count1bits(lfsr & 0x31801) & 0x01)
                lfsr = lfsr << 1 | inbit
                inb <<= 1
                outbyte = outbyte << 1 | outbit
            dataout.append((outbyte ^ 0xFF) & 0xFF)
        return dataout

    @staticmethod
    def __unstuffrev(datain):
        cnt1bits = 0
        obi = 0
        oby = 0
        result = []
        for b in datain:
            for ibi in range(8):
                bit = b & 0x80
                b <<= 1
                if (cnt1bits >= 5) and (bit == 0):
                    cnt1bits = 0
                    continue
                if (bit > 0):
                    cnt1bits += 1
                else:
                    cnt1bits = 0
                oby >>= 1
                oby |= bit
                obi += 1
                if (obi == 8):
                    obi = 0
                    result.append(oby)
                    oby = 0
        if obi > 0:
            result.append(oby >> (8 - obi))

        return result

    @staticmethod
    def decode(msg, rssi, fei):
        if len(msg) < 41:
            return
        msg = EC3000.__descramble(msg)
        print(msg)
        msg = EC3000.__unstuffrev(msg[1:])
        crc = crc_ccitt16(msg[:41])
        if crc != 0xF0B8:
            return
        nibbles = toNibbles(msg)
        if nibbles[0] != 9:
            return
        for n in nibbles[9:13] + nibbles[17:24] + nibbles[62:67] + nibbles[77:78]:
            if n != 0:
                return
        return EC3000(nibbles, rssi, fei)

def decode(rxframe):
    classes = [LaCrosseIT, Bresser7in1, EC3000, EMT7110]
    for cl in classes:
        msg = rxframe[0].copy()
        obj = cl.decode(msg, rxframe[1], rxframe[3])
        if obj:
            return obj
    return
