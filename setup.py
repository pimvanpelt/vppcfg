"""vppcfg setuptools setup.py for pip and deb pkg installations"""
from setuptools import setup

setup(
    name="vppcfg",
    version="0.0.1",
    install_requires=[
        "requests",
        'importlib-metadata; python_version == "3.8"',
        "yamale",
        "netaddr",
        "ipaddress",
        "vpp_papi",
    ],
    packages=["vppcfg", "vppcfg/config", "vppcfg/vpp"],
    entry_points={
        "console_scripts": [
            "vppcfg = vppcfg.vppcfg:main",
        ]
    },
    test_suite="vppcfg.config",
    package_data={"vppcfg": ["*.yaml"]},
)
