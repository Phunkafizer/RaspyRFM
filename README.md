# Python files for RaspyRFM

## connair.py
emulate a gateway for controlling RC socket. Compatible to "Brennenstuhl Brematic", Intertechno "ITGW-433", "ConnAir"
see https://power-switch.eu/

## emoncms.py
receive lacrosse-sensors and post them to the open energy monitor, see https://openenergymonitor.org/

## fs20tx.py
controlling FS20 RX sockets
```sh
sudo ./fs20tx <housecode> <address> <command>
```

## intertechno.py
controlling remote control sockets
```sh
intertechno <HOUSECODE A-P> <GROUP 1-4> <CHANNEL 1-4> on|off
intertechno <12 symbols tristate code>
intertechno <26 bit address> <1 goup bit> <4 bit unit> on|off
intertechno <32 bit code>
usage example:
intertechno A 1 1 on
intertechno 0000FFFF0FFF
interttechno 11110000111100001111000010 0 1110 on
interttechno 11110000111100001111000010010000
```

## lacrosse.py
receiving temperature sensors
```sh
sudo ./lacrosse.py
RFM69 found on CS 1
INIT COMPLETE
Waiting for sensors...
La crosse {'batlo': False, 'AFC': 94, 'init': False, 'T': (19.6, 'C'), 'RSSI': -105, 'RH': (60, '%'), 'ID': '68'}
La crosse {'batlo': False, 'AFC': -118, 'init': False, 'T': (19.5, 'C'), 'RSSI': -98, 'RH': (60, '%'), 'ID': '78'}
La crosse {'batlo': False, 'AFC': 6, 'init': False, 'T': (20.4, 'C'), 'RSSI': -87, 'RH': (58, '%'), 'ID': 'e4'}
La crosse {'batlo': False, 'AFC': 114, 'init': False, 'T': (19.7, 'C'), 'RSSI': -86, 'RH': (57, '%'), 'ID': '24'}
La crosse {'batlo': False, 'AFC': 52, 'init': False, 'T': (19.5, 'C'), 'RSSI': -58, 'RH': (60, '%'), 'ID': '68'}
La crosse {'batlo': False, 'AFC': 14, 'init': False, 'T': (20.5, 'C'), 'RSSI': -97, 'RH': (56, '%'), 'ID': '4'}
La crosse {'batlo': False, 'AFC': 308, 'init': False, 'T': (19.5, 'C'), 'RSSI': -103, 'RH': (60, '%'), 'ID': '68'}
La crosse {'batlo': False, 'AFC': 376, 'init': False, 'T': (19.7, 'C'), 'RSSI': -103, 'RH': (57, '%'), 'ID': '24'}
```

## rcs1000.py
controll Brennenstuhl RC1000 RC sockets
```sh
sudo ./rcs1000.py <5xDIPSWITCH> <CHANNEL 1-4> on|off
```

## rfm69.py
interfacing the RFM69

# Installation
 * [Install GPIO](http://sourceforge.net/projects/raspberry-gpio-python/)
Version has to be >= 0.5.4
 * [Install SPI for Python](http://www.100randomtasks.com/simple-spi-on-raspberry-pi)

## Product
[Module RaspbyRFM Seegel Systeme](http://www.seegel-systeme.de/produkt/raspyrfm-ii/)
