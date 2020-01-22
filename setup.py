#!/usr/bin/env python2.7
import setuptools

setuptools.setup(
	name="RaspyRFM",
	version="1.1",
	author="S. Seegel",
	author_email="post@seegel-systeme.de",
	description="Package for interfacing the RaspyRFM module",
	packages=["RaspyRFM"],
	license="MIT",
	zip_safe=False,
	install_requires=[
		"spidev",
		"RPi.GPIO"
	]
)

