#!/usr/bin/env python
import setuptools

setuptools.setup(
	name="raspyrfm",
	version="1.1",
	author="S. Seegel",
	author_email="post@seegel-systeme.de",
	keywords="RFM69 radio IOT wireless remote hope",
	description="Package for interfacing the RaspyRFM radiomodule",
	url="https://github.com/Phunkafizer/RaspyRFM",
	project_urls={
		"Examples": "https://www.seegel-systeme.de/2015/09/02/ein-funkmodul-fuer-den-raspberry-raspyrfm/"
		},
	packages=["raspyrfm"],
	license="MIT",
	zip_safe=False,
	install_requires=[
		"spidev",
		"rpi-lgpio"
	]
)

