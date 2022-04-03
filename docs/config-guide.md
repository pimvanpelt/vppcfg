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

For the curious, the Yamale syntax validation lives in [this schema](../schema.yaml).
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

Any member sub-interfaces that are added, will automatically be configured to tag-rewrite the
number of tags they have, so a simple dot1q sub-interface will be configured as `pop 1`, while
a QinQ or QinAD sub-interface will be configured as `pop 2`. Conversely, when interfaces are
removed from the bridge, their tag-rewriting will be disabled.

*Caveat*: Currently, bridgedomains are always created with their default attributes in VPP, that
is to say with learning and unicast forwarding turned on, unknown-unicast flooding enabled,
and ARP terminating and aging turned off. In a future release, `vppcfg` will give more
configuration options.

Examples:
```
bridgedomains:
  bd10:
    mtu: 2000
    bvi: loop1
    interfaces: [ BondEthernet0.500, HundredGigabitEthernet12/0/1, vxlan_tunnel1 ]
  bd11:
    description: "No member interfaces, default 1500 byte MTU"
```

### BondEthernets

BondEthernets are required to be named `BondEthernetN` (note the camelcase) where N in
[0,4294967294). The configuration allows the following fields:

*   ***description***: A string, no longer than 64 characters, and excluding the single quote '
    and double quote ". This string is currently not used anywhere, and serves for enduser
    documentation purposes.
*   ***interfaces***: A list of zero or more interfaces that are bond members. The interfaces
    must be PHYs, and in their `interface` configuration, members are allowed only to set the
    MTU.

Note that the configuration object here only specifies the link aggregation and its members.
BondEthernets are expected to occur as well in the `interfaces` section, where their sub-interfaces
and IP addresses and so on are specified.

*Caveat*: Currently, BondEthernets are always created as `LACP` typed devices with a loadbalance
strategy of `l34`. In a future release of `vppcfg`, the type and strategy will be configurable.

Examples:
```
bondethernets:
  BondEthernet0:
    description: "Core: LACP to fsw0.lab.ipng.ch"
    interfaces: [ GigabitEthernet3/0/0, GigabitEthernet3/0/1 ]
```

### VXLAN Tunnels

### Interfaces
