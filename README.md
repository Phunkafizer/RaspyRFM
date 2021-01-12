# Python module & examples for RaspyRFM
![RaspyRFM](img/raspberry-rfm69-ii_6_z4.jpg?raw=true "RasyRFM")

# Installation
```sh
sudo apt-get install git-core python-dev python-pip
git clone https://github.com/Phunkafizer/RaspyRFM.git
cd RaspyRFM
pip install -e .
```
# Examples & applications

## apps/connair.py
emulate a gateway for controlling RC sockets via the app power-switch. Compatible to "Brennenstuhl Brematic", Intertechno "ITGW-433", "ConnAir"
Here you find a python client controlling this gateway: https://github.com/markusressel/raspyrfm-client 

## apps/emoncms.py
receive lacrosse-sensors with the RaspyRFM and post them to the open energy monitor, see https://openenergymonitor.org/

## Receive and send 433 MHz RC remote controls
```sh
apps/rcpulse.py
apps/rcpulse.py -p intertechno -i 47612 -u 1 -a on
apps/rcpulse.py -p logilight -i 76123 -u 1 -a on
apps/rcpulse.py -p pilota -i 1234 -g 1 -u 1 -a on 
```

## Receive 868 MHz ELV FS20 RC remote controls
```sh
apps/rcpulse -f 868.35
```

## rcpulse gateway for controlling & receiving rc-sockets &-remotecontrollers with node-red
```sh
apps/rcpulsegw.py
```

## lacrosse.py
receiving lacrosse temperature sensors IT29-T, IT35-T, ...
```sh
apps/lacrosse.py
RFM69 found on CS 1
INIT COMPLETE
Waiting for sensors...
La crosse {'batlo': False, 'AFC': 94, 'init': False, 'T': (19.6, 'C'), 'RSSI': -105, 'RH': (60, '%'), 'ID': '68'}
La crosse {'batlo': False, 'AFC': 52, 'init': False, 'T': (19.5, 'C'), 'RSSI': -58, 'RH': (60, '%'), 'ID': '68'}
La crosse {'batlo': False, 'AFC': 14, 'init': False, 'T': (20.5, 'C'), 'RSSI': -97, 'RH': (56, '%'), 'ID': '4'}
La crosse {'batlo': False, 'AFC': 308, 'init': False, 'T': (19.5, 'C'), 'RSSI': -103, 'RH': (60, '%'), 'ID': '68'}
La crosse {'batlo': False, 'AFC': 376, 'init': False, 'T': (19.7, 'C'), 'RSSI': -103, 'RH': (57, '%'), 'ID': '24'}
```

## lacrosse gateway apps/lacrossegw.py 
receive lacrosse sensor, visualize in webinterface, save to influxDB

## Product
[Module RaspbyRFM Seegel Systeme](http://www.seegel-systeme.de/produkt/raspyrfm-ii/)

## Blog articles
* [Software installation & examples (german)](http://www.seegel-systeme.de/2015/09/02/ein-funkmodul-fuer-den-raspberry-raspyrfm/)
* [Control RC switches with RaspyRFM (german)](https://www.seegel-systeme.de/2015/09/05/funksteckdosen-mit-dem-raspberry-pi-steuern/)
* [Receive lacrosse sensors (german)](http://www.seegel-systeme.de/2015/02/07/funkthermometer/)
* [Roomclima logger (german)](https://www.seegel-systeme.de/2021/01/11/raumklima-mit-dem-raspberry-pi-ueberwachen-oder-wann-lueften/)
