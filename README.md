#Python files for RaspyRFM
##rfm69.py
interfacing the RFM69
##intertechno.py
controlling remote control sockets
usage example:
'''sh
sudo intertechno.py 0000F0000FFF
'''
##lacrosse.py
receiving temperature sensors
##hamarx.py
receive hama remote controller for remote control sockets
##logilightrx.py
receive logilight remote control
'''sh
sudo ./logilightrx.py
RFM69 found!
INIT COMPLETE
Systemcode 415166 onoff 0 ch 7
Systemcode 415166 onoff 0 ch 7
Systemcode 415166 onoff 0 ch 5
Systemcode 415166 onoff 0 ch 5
'''
##logilighttx.py
control remote control sockets
'''sh
sudo ./logilighttx.py 415166 1 7 4
RFM69 found!
INIT COMPLETE
'''
#Installation
*Install GPIO
(http://sourceforge.net/projects/raspberry-gpio-python/)
Version has to be >= 0.5.4
*Install SPI for Python
(http://www.100randomtasks.com/simple-spi-on-raspberry-pi)
##Product:
[Module RaspbyRFM Seegel Systeme] (http://www.seegel-systeme.de/produkt/raspyrfm-ii/)
