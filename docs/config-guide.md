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
which can then be manipulated as any other interface (eg. have IP addresses, Linux Control Plane
names, sub-interfaces and so on). The same is true for VXLAN tunnels, the only currently supported
tunnel type.

### Loopbacks

Loopbacks are required to be named `loopN` where N is [0,4096). The configuration contains the
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

Examples:
```
loopbacks:
  loop0:
    lcp: "lo0"
    addresses: [ 10.0.0.1/32, 2001:db8::1/128 ]
  loop1:
    lcp: "bvi1"
    addresses: [ 10.0.1.1/24, 10.0.1.2/24, 2001:db8:1::1/64 ]
```

### Bridge Domains

### BondEthernets

### Interfaces

### VXLAN Tunnels
