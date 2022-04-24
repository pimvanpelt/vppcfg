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
""" A vppcfg configuration module that validates Linux Control Plane (lcp) elements """


def get_lcps(yaml, interfaces=True, loopbacks=True, bridgedomains=True):
    """Returns a list of LCPs configured in the system. Optionally (de)select the different
    types of LCP. Return an empty list if there are none of the given type(s)."""

    ret = []
    if interfaces and "interfaces" in yaml:
        for _ifname, iface in yaml["interfaces"].items():
            if "lcp" in iface:
                ret.append(iface["lcp"])
            if "sub-interfaces" in iface:
                for _subid, sub_iface in iface["sub-interfaces"].items():
                    if "lcp" in sub_iface:
                        ret.append(sub_iface["lcp"])

    if loopbacks and "loopbacks" in yaml:
        for _ifname, iface in yaml["loopbacks"].items():
            if "lcp" in iface:
                ret.append(iface["lcp"])
    if bridgedomains and "bridgedomains" in yaml:
        for _ifname, iface in yaml["bridgedomains"].items():
            if "lcp" in iface:
                ret.append(iface["lcp"])

    return ret


def is_unique(yaml, lcpname):
    """Returns True if there is at most one occurence of the LCP name in the entire config."""

    lcps = get_lcps(yaml)
    return lcps.count(lcpname) < 2
