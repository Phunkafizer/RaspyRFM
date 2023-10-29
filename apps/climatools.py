#!/usr/bin/env python
import math


def calcHelperParams(t, ice):
	if t >= 0:
		return (7.5, 237.3)

	if ice:
		return (9.5, 265.6)

	return (7.6, 240.7)

def calcSVP(t, ice = False):
	'''
	calculate saturation vapor pressure from given temperature

	:param t: temperature in °C
	:param ice: for temperatures < 0 °C, True for ice, False for water

	:result: saturation vapor pressure in hPa
	'''
	a, b = calcHelperParams(t, ice)
	return 6.1078 * 10**(a*t/(b+t))

def calcVP(t, rh, ice = False):
	'''
	calculate vapor pressure from tempearture and rel. humidity

	:param t: temperature in °C
	:param rh: relative humidit in %
	:param ice: for temperatures < 0 °C, True for ice, False for water

	:result: vapor pressure in hPa

	'''
	return rh / 100 * calcSVP(t, ice)

def calcDewPoint(t, rh, ice = False, atRh = 100):
	'''
	calculate dewpoint (atRh = 100)
	or temperature for given rel. humidity
	'''
	vp = calcVP(t, rh, ice)* 100 / atRh
	a, b = calcHelperParams(t, ice)
	v = math.log10(vp / 6.1078)
	return round(b*v/(a-v), 1)

def calcAH(t, rh, ice = False):
	'''
	calculate absolute humidity

	:param t: temperature in °C
	:param rh: relative humidit in %
	:param ice: for temperatures < 0 °C, True for ice, False for water

	:result: absolute humidity in g/m³
	'''
	return round(10**5 * 18.016/8314.3 * calcVP(t, rh, ice)/(t+273.15), 1)

def calcAw(t, rh, tSurf, ice = False):
	'''
	calculate activity of water for given surface temperature

	:param t: current temperature in °C
	:param rh: current relative humidity in %
        :param tSurf: current temperature in °C of surface

	:result: aw in %
	'''
	aw = calcSVP(t, ice) / calcSVP(tSurf, ice) * rh
	return aw if aw <= 100 else 100

if __name__ == '__main__':
    t = 23.4
    rh = 55
    ice = False
    tSurf = 18

    print(f"Temperatur:            {t:.1f} °C")
    print(f"rel. Luftfeuchtigkeit: {rh} %")
    print(f"Oberfl. Temp.:         {tSurf:.1f} °C")
    print(f"Sättigungsdampfdruck:  {calcSVP(t, ice):.1f} hPa")
    print(f"Dampfdruck:            {calcVP(t, rh, ice):.1f} hPa")
    print(f"Taupunkt:              {calcDewPoint(t, rh, ice):.1f} °C")
    print(f"TF-80:                 {calcDewPoint(t, rh, ice, 80):.1f} °C")
    print(f"TF-60:                 {calcDewPoint(t, rh, ice, 60):.1f} °C")
    print(f"aw Wert:               {calcAw(t, rh, tSurf, ice):.0f} %")
    for ti in range(0, 30, 5):
        print(ti, calcAw(t, rh, ti, ice))
