from __future__ import print_function
import spidev

class RfmBase():
	@staticmethod
	def scan():
		spi = spidev.SpiDev()
		result = []
		for cs in range(4):
			try:
				spi.open(0, cs)
				spi.max_speed_hz = 5000
				v = spi.xfer3([0x10, 0x10])[1] #try to read version register of RFM69
				if v == 0x24:
					result.append(v)
					spi.close()
					continue

				v = spi.xfer3([0x42, 0x10])[1]
				if v == 0x12:
					result.append(v)
					spi.close()
					continue

				result.append(None)
				spi.close()
			except:
				spi.close()
				break

		return result

	@staticmethod
	def test(cs, version):
		d = RfmBase.scan()
		if len(d) < cs + 1:
			return False

		return d[cs] == version

	def __init__(self, cs):
		self.__spi = spidev.SpiDev()
		self.__spi.open(0, cs)
		self.__spi.max_speed_hz=int(2E6)
	
	def read_reg(self, reg):
		temp = self.__spi.xfer3([reg & 0x7F, 0x00])
		return int(temp[1])

	def _write_reg(self, reg, val):
		temp = self.__spi.xfer3([(reg & 0x7F) | 0x80, int(val & 0xFF)])

	def _write_reg_word(self, reg, val):
		self._write_reg(reg, (val >> 8) & 0xFF)
		self._write_reg(reg + 1, val & 0xFF)

	def _set_reg(self, reg, mask, val):
		temp = self.read_reg(reg) & (~mask)
		temp |= val & mask
		self._write_reg(reg, temp)

	def read_fifo_burst(self, len):
		temp = self.__spi.xfer3([0x00] + [0x00] * len)
		return temp[1:]

	def write_fifo_burst(self, data):
		self.__spi.xfer3([0x80] + list(data))

	def read_reg_word(self, reg):
		temp = self.__spi.xfer3([reg & 0x7F, 0x00, 0x00])
		return (temp[1] << 8) | (temp[2])