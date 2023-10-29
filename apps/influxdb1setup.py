#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
This prepares an InfluxDB1 database for 868gw.py
'''

INFLUXDB_HOST = "127.0.0.1"
INFLUXDB_PORT = 8086
INFLUXDB_USER = "admin"
INFLUXDB_PASS = "admin"

INFLUXDB_DATABASE = "mysensors"

from influxdb import InfluxDBClient
ic = InfluxDBClient(
    host=INFLUXDB_HOST,
    port=INFLUXDB_PORT,
    username=INFLUXDB_USER,
    password=INFLUXDB_PASS
)

ic.create_database(INFLUXDB_DATABASE)
ic.switch_database(INFLUXDB_DATABASE)

ic.create_retention_policy("rp_3h", duration="3h", replication=1, default=True)
ic.create_retention_policy("rp_1w", duration="1w", replication=1, shard_duration='24h')
ic.create_retention_policy("rp_1y", duration="365d", replication=1, shard_duration='1w')
ic.create_continuous_query("cq_3m", 'SELECT mean(*) INTO "rp_1w".:MEASUREMENT from /.*/ GROUP BY time(3m),*')
ic.create_continuous_query("cq_3h", 'SELECT mean(*) INTO "rp_1y".:MEASUREMENT from rp_1w./.*/ GROUP BY time(3h),*')
