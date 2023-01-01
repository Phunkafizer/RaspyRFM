from __future__ import print_function

import datetime

def crc8(buf):
        crc = 0
        for j in range(5):
                crc = crc ^ buf[j]
                for i in range(8):
                        if (crc & 0x80 == 0x80):
                                crc = (crc << 1) ^ 0x31
                        else:
                                crc <<= 1
        return crc & 0xFF

def csum(data):
        s = 0
        for i in range(12):
                s += data[i]
        return s & 0xFF

class rawsensor(object):
        def __init__(self, data):
                self._data = {}
                self._data['timestamp'] = datetime.datetime.now().replace(microsecond=0).isoformat()
                self.__raw = data

        def __str__(self):
                res = 'RAW RSSI ' + str(self.__raw[1]) + " dBm: "
                for data in self.__raw[0]:
                    res = res + ' ' + hex(data)[2:];
                return res;

        def GetData(self):
                return self._data

        @staticmethod
        def CreateSensor(data):
                obj = lacross.Create(data)
                if (obj):
                        return obj

                obj = emt7110.Create(data)
                if (obj):
                        return obj

                return rawsensor(data)

class lacross(rawsensor):
        def __init__(self, data):
                rawsensor.__init__(self, data)
                id = data[0][0] << 4 | data[0][1] >> 4
                self._data['ID'] = hex(id & 0xFC)[2:]
                self._data['init'] = bool(id & 1<<1)
                self._data['T'] = (10 * ((data[0][1] & 0xF) - 4) + (data[0][2] >> 4) + (data[0][2] & 0xF) / 10.0, 'C')
                rh = data[0][3] & 0x7F
                if (rh > 0) and (rh <= 100):
                        self._data['RH'] = (rh, '%')
                self._data['batlo'] = bool(data[0][3] & 1<<7)
                self._data['RSSI'] = data[1]
                self._data['AFC'] = data[2]
                self._data['FEI'] = data[3]

        def __str__(self):
                res = 'La crosse ' + str(self._data)
                return res;

        @staticmethod
        def Create(data):
                if (len(data[0]) < 5) or (crc8(data[0]) != 0):
                    return
                if (data[0][1] & 0x0F > 9) or (data[0][2] >> 4 > 9) or (data[0][2] & 0x0F > 9):
                    return
                return lacross(data)

class emt7110(rawsensor):
        def __init__(self, data):
                rawsensor.__init__(self, data)
                _data = data[0]
                id = _data[0] << 24 | _data[1] << 16 | _data[2] << 8 | _data[3]
                self._data['ID'] = hex(id)[2:]
                self._data['P'] = (((_data[4] << 8 | _data[5]) & 0x3FFF) / 2.0, 'W')
                self._data['U'] = (_data[8] / 2.0 + 128, 'V')
                self._data['I'] = (_data[6] << 8 | _data[7], 'mA')
                self._data['W'] = (((_data[9] << 8 | _data[10]) & 0x3FFF) / 100, 'kWh')

        def __str__(self):
                return 'emt7110 ' + str(self._data)

        @staticmethod
        def Create(data):
                if len(data[0]) >= 12 and len(data[0]) <= 20 and csum(data[0]) == 0:
                        return emt7110(data)
