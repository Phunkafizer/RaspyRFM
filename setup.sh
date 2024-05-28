#!/bin/bash

PCKS="python3 python3-dev python3-pip python3-venv"

#check if all required packages are installed
for pck in $PCKS; do
	status="$(dpkg-query -W --showformat='${db:Status-Status}' "$pck" 2>&1)"
	if [ ! $? = 0 ] || [ ! "$status" = installed ]; then
		sudo apt install $pck
	fi
done

python3 -m venv .env
source .env/bin/activate
pip3 install paho-mqtt
pip3 install influxdb
pip3 install influxdb-client
pip3 uninstall RPi.GPIO
pip3 install rpi-lgpio
pip3 install -e .
apps/scan.py
