# Python module & examples for RaspyRFM
![RaspyRFM](img/raspberry-rfm69-ii_6_z4.jpg?raw=true "RasyRFM")

#Installation
```sh
sudo su
apt-get install git-core python-dev
apt-get install python-pip

cd <downloaded RaspyRFM code> #folder in which setup.py is located
pip install -e .
```

#Using python module and set parameters
```python
import RasyRFM
rfm = RaspyRFM(1, RFM69)
rfm.set_params(
        Freq = 868.300, #MHz center frequency
        ModulationType = rfm69.FSK, #modulation
        Datarate = 9.992, #kbit/s baudrate
        Deviation = 19.042, #kHz frequency deviation
        SyncPattern = [0xc6, 0x26, 0xc6, 0x26], #syncword
        Bandwidth = 100, #kHz bandwidth
        RssiThresh = -105, #dBm RSSI threshold
		TXPower = 13, #dBm
		Preamble = 2, #bytes
)
```

## connair.py
emulate a gateway for controlling RC sockets via the app power-switch. Compatible to "Brennenstuhl Brematic", Intertechno "ITGW-433", "ConnAir"
see https://power-switch.eu/

## emoncms.py
receive lacrosse-sensors with the RaspyRFM and post them to the open energy monitor, see https://openenergymonitor.org/

## fs20tx.py
controlling FS20 RX sockets
```sh
sudo ./fs20tx <housecode> <address> <command>
```

## intertechno.py
controlling remote control sockets
```sh
rcpulse <HOUSECODE A-P> <GROUP 1-4> <CHANNEL 1-4> on|off #control old intertechno sockets
rcpulse <12 symbols tristate code> #control old intertechno sockets
rcpulse <26 bit address 0|1> <1 goup bit 0|1> <4 bit unit 0|1> on|off #control intertechno self learning
rcpulse <32 bit code 0|1> #control intertechno and compatible (HAMA, REV)
rcpulse <5 DIP 0|1> <channel 1-4> on|off #control Brennenstuhl RC1000 
usage example:
./rcpulse A 1 1 on
./rcpulse 0000FFFF0FFF
./rcpulse 11110000111100001111000010 0 1110 on
./rcpulse 11110000111100001111000010010000
```

## Receive 433 MHz RC remote controls
```sh
./rcpulse.py
```

## Receive 868 MHz ELV FS20 RC remote controls
```sh
./rcpulse -f 868.35
```

## lacrosse.py
receiving lacrosse temperature sensors IT29-T, IT35-T, ...
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

## Product
[Module RaspbyRFM Seegel Systeme](http://www.seegel-systeme.de/produkt/raspyrfm-ii/)
