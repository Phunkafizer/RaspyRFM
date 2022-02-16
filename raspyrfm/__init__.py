from . import rfmbase
from . import rfm69

RFM69 = 1
RFM95_96 = 2

def __get_hw_params(mod):
	if mod == 1:
		dio0 = 25
	elif mod == 2:
		dio0 = 24
	elif mod == 3:
		dio0 = 1
	elif mod == 4:
		dio0 = 18
	else:
		return

	return (mod - 1, dio0)

def RaspyRFM(mod, type):
	""" Create a RaspyRFM object.

	Parameters:
		mod (int): 
			Number of the module.
			Always 1 for a single RaspyRFM
			1-2 for a dual RaspyRFM
			1-4 for a quad RaspyRFM

		type (int):
			type of the module (RFM69 or RFM9x)

	Returns:
		Rfm69 or Rfm9x object if successful, otherwise None

	"""
	if not raspyrfm_test(mod, type):
		return None

	s = __get_hw_params(mod)

	if s:
		if type == RFM69:
			return rfm69.Rfm69(s[0], s[1])
		else:
			print("Not yet implemented.")

	return None

def raspyrfm_test(mod, type):
	if mod < 1:
		return False

	d = rfmbase.RfmBase.scan()
	if len(d) < mod:
		return False

	v = d[mod - 1]
	if (type == RFM69) and (v == 0x24):
		return True

	if (type == RFM95_96) and (v == 0x12):
		return True

	return False