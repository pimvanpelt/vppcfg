#
# Copyright (c) 2022 Pim van Pelt
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""" A vppcfg configuration module that validates MAC addresses """
import netaddr


def is_valid(mac):
    """Return True if the string given in `mac` is a valid (6-byte) MAC address,
    as defined by netaddr.EUI"""
    try:
        _addr = netaddr.EUI(mac)
    except netaddr.core.AddrFormatError:
        return False
    return True


def is_local(mac):
    """Return True if a MAC address is a valid locally administered one."""
    try:
        addr = netaddr.EUI(mac)
    except netaddr.core.AddrFormatError:
        return False
    return bool(addr.words[0] & 0b10)


def is_multicast(mac):
    """Return True if a MAC address is a valid multicast one."""
    try:
        addr = netaddr.EUI(mac)
    except netaddr.core.AddrFormatError:
        return False
    return bool(addr.words[0] & 0b01)


def is_unicast(mac):
    """Return True if a MAC address is a valid unicast one."""
    try:
        addr = netaddr.EUI(mac)
    except netaddr.core.AddrFormatError:
        return False
    return not bool(addr.words[0] & 0b01)
