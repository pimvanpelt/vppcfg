# A VPP Configuration Utility

## Configuration Guide

`vppcfg` consumes YAML files of a specific format. Their validity is asserted by two main
types of validation: 

1.  syntax checks are performed by [Yamale](https://github.com/23andMe/Yamale/) and this
    ensures that all fields in the YAML file are correctly formed, that field-names are
    correctly spelled, that no extra fields are given, and their values are of the correct
    type.
1.  semantic validations are performed to ensure that configurations are safely applyable
    to a running VPP. *Note*: Some semantic checks are stricter than VPP, because applying
    them may leave the dataplane in a non-recoverable state.

For the curious, the Yamale syntax validation lives in [this schema](../vppcfg/schema.yaml).
If you want to get started quickly and don't mind cargo-culting, take a look at [this example](../example.yaml).

### Basic structure

The YAML configuration file has the following structure, consisting of several _maps_ of
a given object _type_, which specify _names_ of those objects:

```
loopbacks:
  loop0:
    [ Loopback Configuration ]

bondethernets:
  BondEthernet0:
    [ BondEthernet (bond) Configuration ]

vxlan_tunnels:
  vxlan_tunnel0:
    [ VXLAN (tunnel) Configuration ]

bridgedomains:
  bd1:
    [ BridgeDomain Configuration ]

interfaces:
  GigabitEthernet3/0/0:
    [ Interface Configuration ]
  BondEthernet0:
    [ BondEthernet (interface) Configuration ]
  vxlan_tunnel0:
    [ VXLAN (interface) Configuration ]
```

Object _names_ are strictly enforced, they must be unique in their scope, and they are case sensitive.
For example, any loopback MUST be named `loopN`, and any bondethernet MUST be named `BondEthernetN`
(note here the camel case). A distinction is made between the object and the resulting interface:
A BondEthernet occurs twice in the configuration. The first time, in the `bondethernets` section, the
bond configuration is specified. That bond configuration yields an interface in VPP named BondEthernetN,
which occurs in the `interfaces` section where it can then be manipulated like any other interface (eg.
have IP addresses, Linux Control Plane names, sub-interfaces and so on). The same is true for VXLAN
tunnels, the only currently supported tunnel type.

### Loopbacks

Loopbacks are required to be named `loopN` where N in [0,4096). The configuration allows the
following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***lcp***: A Linux Control Plane interface pair _LIP_. If specified, the loopback will be
    presented in Linux under this name. Its name may be at most 15 characters long, and match
    the regular expression `[a-z]+[a-z0-9-]*`.
*   ***mtu***: An integer value between [128,9216], noting the (packet) MTU of the loopback. It
    will default to 1500 if not specified.
*   ***addresses***: A list of between one and six IPv4 or IPv6 addresses including prefixlen
    in CIDR format. VPP requires IP addresses to be unique in the entire dataplane, with one
    notable exception: Multiple IP addresses in the same prefix/len can be added on one and the
    same interface.

Although VPP would allow it, `vppcfg` does not allow for loopbacks to have sub-interfaces.

Examples:
```
loopbacks:
  loop0:
    description: "loopback with default 1500 byte MTU"
    lcp: lo0
    addresses: [ 10.0.0.1/32, 2001:db8::1/128 ]
  loop1:
    lcp: bvi1
    mtu: 9000
    addresses: [ 10.0.1.1/24, 10.0.1.2/24, 2001:db8:1::1/64 ]
```

### Bridge Domains

BridgeDomains are required to be named `bdN` where N in [1, 16777216). Note that bridgedomain
`bd0` is reserved and cannot be used. The configuration allows the following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***mtu***: An integer value between [128,9216], noting the (packet) MTU of the bridgedomain.
    It will default to 1500 if not specified. All member interfaces, including the `BVI`, are
    required to have the same MTU as their bridge.
*   ***bvi***: An optional _bridge virtual interface_ (sometimes also referred to as an _IRB_)
    which refers to an existing loopback interface by name (ie `loop0`).
*   ***interfaces***: A list of zero or more interfaces or sub-interfaces that are bridge
    members. If the bridge has a `BVI`, it MUST NOT appear in this list. Bridges are allowed to
    exist with no member interfaces.
*   ***settings***: A map of bridge-domain settings to further manipulate its behavior:
    *   ***learn***: A boolean that turns learning on/off. Default True.
    *   ***unicast-flood***: A boolean that turns unicast flooding on/off. Default True.
    *   ***unknown-unicast-flood***: A boolean that turns unknown unicast flooding on/off.
        Default True.
    *   ***unicast-forward***: A boolean that turns unicast forwarding on/off. Default True.
    *   ***arp-termination***: A boolean that turns termination and response of ARP Requests
        on/off. Default False.
    *   ***arp-unicast-forward***: A boolean that turns L2 arp-unicast forwarding on/off.
        Default False.
    *   ***mac-age-minutes***: An integer between [0,256) that drives the ARP timeout on the
        bridge in minutes, where 0 means do not age out, which is the default.

Any member sub-interfaces that are added, will automatically be configured to tag-rewrite the
number of tags they have, so a simple dot1q sub-interface will be configured as `pop 1`, while
a QinQ or QinAD sub-interface will be configured as `pop 2`. Conversely, when interfaces are
removed from the bridge, their tag-rewriting will be disabled.

Examples:
```
bridgedomains:
  bd10:
    mtu: 2000
    bvi: loop1
    interfaces: [ BondEthernet0.500, HundredGigabitEthernet12/0/1, vxlan_tunnel1 ]
  bd11:
    description: "No members, default 1500 byte MTU, with (default) settings"
    settings:
      learn: True
      unicast-flood: True
      unknown-unicast-flood: True
      unicast-forward: True
      arp-termination: False
      arp-unicast-forward: False
      mac-age-minutes: 0
```

*Caveat*: The flooding of unknown-unicast can be turned on or off, but flooding to a specific interface
(as opposed to all interfaces which is the default), is not supported.

### BondEthernets

BondEthernets are required to be named `BondEthernetN` (note the camelcase) where N in
[0,4294967294). The configuration allows the following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***interfaces***: A list of zero or more interfaces that are bond members. The interfaces
    must be PHYs, and in their `interface` configuration, members are allowed only to set the
    MTU.
*   ***mode***: A mode to run the LAG in. Can be one of 'round-robin', 'active-backup', 'xor',
    'broadcast' or 'lacp'. The default is LACP.
*   ***load-balance***: A loadbalancing strategy to use, if the mode is either XOR or LACP.
    Can be one of 'l2', 'l23', or 'l34'. The default is l34, which hashes on the source and
    destination IPs and ports.

Note that the configuration object here only specifies the link aggregation and its members.
BondEthernets are expected to occur as well in the `interfaces` section, where their sub-interfaces
and IP addresses and so on are specified.

Examples:
```
bondethernets:
  BondEthernet0:
    description: "Core: LACP to fsw0.lab.ipng.ch"
    interfaces: [ GigabitEthernet1/0/0, GigabitEthernet1/0/1 ]
    mode: lacp
    load-balance: l2
  BondEthernet1:
    description: "Core: RR LAG"
    interfaces: [ GigabitEthernet3/0/0, GigabitEthernet3/0/1 ]
    mode: round-robin
```

### VXLAN Tunnels

VXLAN Tunnels are required to be named `vxlan_tunnelN` (note the underscore), where N in
[0,2G). The configuration allows the following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***local***: A required IPv4 or IPv6 address for our (source) side of the tunnel.
*   ***remote***: A required IPv4 or IPv6 address for their (destination) side of the tunnel.
*   ***vni***: A _Virtual Network Indentifier_, a required integer number between [1,16M).

Local and Remote sides of the tunnel MUST have the same address family.

*Caveat*: VXLAN tunnels are currently only possible as unicast (src/dst), with static source
and destination ports (4789), and with a `decap-next` of L2. Also, VNIs must be globally unique.
In a future release of `vppcfg`, these fields will be configurable, and VNI reuses will be
allowed between different dst endpoints.

Examples:
```
vxlan_tunnels:
  vxlan_tunnel0:
    description: "Some IPv6 VXLAN tunnel"
    local: 2001:db8::1
    remote: 2001:db8::2
    vni: 100
  vxlan_tunnel1:
    local: 192.0.2.1
    remote: 192.0.2.2
    vni: 101
```

### TAPs

TAPs are virtual L2 (and sometimes L3) devices in the kernel, that are backed by a userspace
program. VPP can create a TAP and expose them in a network namespace, and optionally add them
to a (Linux) bridge.

TAPs are required to be named `tapN` where N in [0,1024], but be aware that Linux CP will use TAPs
with an instance id that equals their hardware interface id. It is safer to create TAPs from the top
of the namespace, for example `tap100`, see the caveat below on why. The configuration then allows
for the following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***host***: Configuration of the Linux side of the TAP:
    *    ***name***: A (mandatory) Linux interface name, at most 15 characters long, matching the
         regular expression `[a-z]+[a-z0-9-]*`.
    *    ***mac***: The MAC address for the Linux interface, if empty it will be randomly assigned.
    *    ***mtu***: The MTU of the Linux interface, if empty it will be set to 1500.
    *    ***bridge***: An optional Linux bridge to add the Linux interface into. Note: VPP will
         expect this bridge to exist, otherwise the addition will silently fail after creating the TAP.
    *    ***namespace***: An optional Linux network namespace in which to add the Linux interface,
         which can be empty (the default) in which case the Linux interface is created in the default
         namespace.
    *    ***bridge-create***: A boolean that determines if vppcfg will create the bridge in the namespace
         if it does not yet exist, and will set its MTU to the `host.mtu` value if it does exist.
         Defaults to False, and can only be True if `bridge` is given.
    *    ***namespace-create***: A boolean that determines if vppcfg will create the network namespace
         if it does not yet exist. Defaults to False, and can only be True if `namespace` is given.
*   ***rx-ring-size***: An optional RX ringbuffer size, a value from 8 to 32K, must be a power of two.
    If it is not specified, it will default to 256.
*   ***tx-ring-size***: An optional TX ringbuffer size, a value from 8 to 32K, must be a power of two.
    If it is not specified, it will default to 256.

*NOTE*: The Linux Controlplane (LCP) plugin in VPP also uses TAPs to expose the dataplane (sub-)
interfaces in Linux, but for that functionality, refer to the `lcp` fields in interfaces and loopbacks.

*Caveat*: syncing changed attributes (with the exception of the bridge name) after the TAP was created
is not supported. This is because there are no API setters in VPP. Changing attributes is possible, but
operators should expect that the TAP interface gets pruned and recreated.

*Caveat*: `vppcfg` will try to ensure a TAP is not created with the same instance ID as a hardware
interface, but it can not make strict guarantees, because there exists no API to look the hardware
interface id's up.  As a rule of thumb, start TAPs at twice the total count of hardware interfaces
(PHYs, BondEthernets, VXLAN Tunnels and other TAPs) in the config.

Examples:
```
taps:
  tap100:
    description: "TAP with MAC, MTU and Bridge"
    host:
      name: vpp-tap100
      mac: f6:18:fe:e7:d2:3a
      mtu: 9000
      namespace: test
      namespace-create: True
      bridge: vpp-br0
      bridge-create: True
    rx-ring-size: 1024
    tx-ring-size: 512
```


### Interfaces

Interfaces and their sub-interfaces are configured very similarly. Interface names MUST either
exist as a PHY in VPP (ie. `HundredGigabitEthernet12/0/0`) or as a specified `BondEthernetN` or
`vxlan_tunnel0` device. The configuration allows the following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***lcp***: A Linux Control Plane interface pair _LIP_. If specified, the interface will be
    presented in Linux under this name. Its name may be at most 15 characters long, and match
    the regular expression `[a-z]+[a-z0-9-]*`. In sub-interfaces, a _LIP_ may only be specified
    if its direct parent has an _LIP_ as well. In the case of a QinQ or QinAD sub-interface, there
    must exist an intermediary interface with the correct encapsulation, and it too must have a
    _LIP_.
*   ***mtu***: An integer value between [128,9216], noting the MTU of the interface. The MTU for
    a PHY will be set as its Max Frame Size in addition to its packet MTU. Parents must always have
    a larger MTU than any of their children (this is done to satisfy Linux Control Plane).
*   ***addresses***: A list of between one and six IPv4 or IPv6 addresses including prefixlen
    in CIDR format. VPP requires IP addresses to be unique in the entire dataplane, with one
    notable exception: Multiple IP addresses in the same prefix/len can be added on one and the
    same interface.
*   ***l2xc***: A Layer2 Cross Connect interface name. An `l2xc` will be configured, after which
    this interface cannot have any L3 configuration (IP addresses or LCP), and neither can the
    target interface.
*   ***state***: An optional string that configures the link admin state, either `up` or `down`.
    If it is not specified, the link is considered admin 'up'.
*   ***device-type***: An optional interface type in VPP. Currently the only supported vlaue is
    `dpdk`, and it is used to generate correct mock interfaces if the `--novpp` flag is used.

Further, top-level interfaces, that is to say those that do not have an encapsulation, are permitted
to have any number of sub-interfaces specified by `subid`, an integer between [0,2G), which further
allow the following field:
*   ***encapsulation***: An encapsulation for the sub-interface:
    *   ***dot1q***: An outer Dot1Q tag, an integer between [1,4096).
    *   ***dot1ad***: An outer Dot1AD tag, an integer between [1,4096).
    *   ***inner-dot1q***: An inner Dot1Q tag, an integer between [1,4096).
    *   ***exact-match***: A boolean, signalling the sub-interface should match on the exact number
        of tags specified. This is required for any L3 interface (carrying an IP address or LCP),
        but allowed to be False for L2 interfaces (ie. bridge-domain members or L2XC targets).

It's permitted to omit the `encapsulation` fields, in which case an exact-matching Dot1Q
encapsulation with tag value equal to the `subid` will be configured. Obviously, it is forbidden
to specify both `dot1q` and `dot1ad` fields at the same time.

Examples:
```
interfaces:
  HundredGigabitEthernet12/0/0:
    device-type: dpdk
    lcp: "ice0"
    mtu: 9000
    addresses: [ 192.0.2.1/30, 2001:db8:1::1/64 ]
    sub-interfaces:
      1234:
        mtu: 9000
        lcp: "ice0.dot1q"
        addresses: [ 192.0.2.5/30, 2001:db8:2::1/64 ]
      1235:
        mtu: 1500
        lcp: "ice0.qinq"
        addresses: [ 192.0.2.9/30, 2001:db8:3::1/64 ]
        encapsulation:
          dot1q: 1234
          inner-dot1q: 1000
          exact-match: True

  BondEthernet0:
    mtu: 9000
    lcp: "bond0"
    sub-interfaces:
      100:
        mtu: 2500
        l2xc: BondEthernet0.200
        encapsulation:
           dot1q: 100
           exact-match: False
      200:
        mtu: 2500
        l2xc: BondEthernet0.100
        encapsulation:
           dot1q: 200
           exact-match: False
```
