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

### NOTE(pim): The source of truth of this string lives in ../schema.yaml
###            Make sure to include it here, verbatim, if it ever changes.
yamale_schema = r"""
interfaces: map(include('interface'),key=str(),required=False)
bondethernets: map(include('bondethernet'),key=str(matches='BondEthernet[0-9]+'),required=False)
loopbacks: map(include('loopback'),key=str(matches='loop[0-9]+'),required=False)
bridgedomains: map(include('bridgedomain'),key=str(matches='bd[0-9]+'),required=False)
vxlan_tunnels: map(include('vxlan'),key=str(matches='vxlan_tunnel[0-9]+'),required=False)
---
vxlan:
  description: str(exclude='\'"',len=64,required=False)
  local: ip()
  remote: ip()
  vni: int(min=1,max=16777215)
---
bridgedomain:
  description: str(exclude='\'"',len=64,required=False)
  mtu: int(min=128,max=9216,required=False)
  bvi: str(matches='loop[0-9]+',required=False)
  interfaces: list(str(),required=False)
  settings: include('bridgedomain-settings',required=False)
---
bridgedomain-settings:
  learn: bool(required=False)
  unicast-flood: bool(required=False)
  unknown-unicast-flood: bool(required=False)
  unicast-forward: bool(required=False)
  arp-termination: bool(required=False)
  arp-unicast-forward: bool(required=False)
  mac-age-minutes: int(min=0,max=255,required=False)
---
loopback:
  description: str(exclude='\'"',len=64,required=False)
  lcp: str(max=15,matches='[a-z]+[a-z0-9-]*',required=False)
  mtu: int(min=128,max=9216,required=False)
  addresses: list(ip_interface(),min=1,max=6,required=False)
---
bondethernet:
  description: str(exclude='\'"',len=64,required=False)
  interfaces: list(str(matches='.*GigabitEthernet[0-9]+/[0-9]+/[0-9]+'))
---
interface:
  description: str(exclude='\'"',len=64,required=False)
  mac: mac(required=False)
  lcp: str(max=15,matches='[a-z]+[a-z0-9-]*',required=False)
  mtu: int(min=128,max=9216,required=False)
  addresses: list(ip_interface(),min=1,max=6,required=False)
  sub-interfaces: map(include('sub-interface'),key=int(min=1,max=4294967295),required=False)
  l2xc: str(required=False)
  state: enum('up', 'down', required=False)
---
sub-interface:
  description: str(exclude='\'"',len=64,required=False)
  lcp: str(max=15,matches='[a-z]+[a-z0-9-]*',required=False)
  mtu: int(min=128,max=9216,required=False)
  addresses: list(ip_interface(),required=False)
  encapsulation: include('encapsulation',required=False)
  l2xc: str(required=False)
  state: enum('up', 'down', required=False)
---
encapsulation:
  dot1q: int(min=1,max=4095,required=False)
  dot1ad: int(min=1,max=4095,required=False)
  inner-dot1q: int(min=1,max=4095,required=False)
  exact-match: bool(required=False)
"""
