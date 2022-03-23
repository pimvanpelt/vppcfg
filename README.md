# A VPP Configuration Utility

This tool reads a configuration file, checks it for syntax and semantic correctness, and then
reconciles a running [VPP](https://fd.io/) daemon with its configuration. It is meant to be
re-entrant and stateless. The tool connects to the VPP API and creates/removes all of the
configuration in a minimally intrusive way.

***NOTE*** This code is under development, and probably won't work well until this note is removed.
If you're interested in helping, reach out to &lt;pim at ipng dot ch&gt; to discuss options.

## Building

This program expects Python3 and PIP to be installed. It's known to work on OpenBSD and Debian.

```
sudo pip3 install argparse
sudo pip3 install yamale
sudo pip3 install pyyaml
sudo pip3 install pyinstaller

## Ensure all unittests pass.
./tests.py -t unittest/*.yaml

## Build the tool
pyinstaller vppcfg  --onefile
```

## Running

```
dist/vppcfg -h
usage: vppcfg [-h] -c CONFIG [-s SCHEMA] [-d]

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        YAML configuration file for VPP
  -s SCHEMA, --schema SCHEMA
                        YAML schema validation file
  -d, --debug           Enable debug, default False
```

## Design

### YAML Configuration

The main file that is handled by this program is the **Configuration File**.

## Validation

There are three types of validation: _schema_ which ensures that the input YAML has the correct
fields of well known types, _semantic_ which ensures that the configuration doesn't violate
semantic constraints and _runtime_ which ensures that the configuration can be applied to the
VPP daemon.

### Schema Validators

First the configuration file is held against a structural validator, provided by [Yamale](https://github.com/23andMe/Yamale/).
Based on a validation schema in `schema.yaml`, the input file is checked for syntax correctness.
For example, a `dot1q` field must be an integer between 1 and 4095, wile an `lcp` string must
match a certain regular expression. After this first pass of syntax validation, I'm certain that
_if_ a field is set, it is of the right type (ie. string, int, enum). 

### Semantic Validators

A set of semantic validators, each with a unique name, ensure that the _semantics_ of the YAML
are correct. For example, a physical interface cannot have an LCP, addresses or sub-interfaces,
if it is to be a member of a BondEthernet.

Validators are expected to return a tuple of (bool,[string]) where the boolean signals success
(False meaning the validator rejected the configuration file, True meaning it is known to be
correct), and a list of zero or more strings which contain messages meant for human consumption.

### Runtime Validators

After the configuration file is considered syntax and semanticly valid, there is one more set of
checks to perform -- runtime validators ensure that the configuration elements such as physical
network devices (ie. `HundredGigabitEthernet12/0/0` or plugin `lcpng` are present on the system.
It does this by connecting to VPP and querying the runtime state to ensure that what is modeled
in the configuration file is able to be committed.

## Unit Tests

It is incredibly important that changes to this codebase, particularly the validators, are well
tested. Unit tests are provided in the `unittests/` directory with a Python test runner in
`tests.py`. A test is a two-document YAML file, the first document describes the unit test
and the second document is a candidate configuration file to test.

The format of the unit test is as follows:
```
test:
  description: str()
  errors:
    expected: list(str())
    count: int()
---
<some YAML config contents>
```

Fields:
*   ***description***: A string describing the behavior that is being tested against. Any failure
    of the unittest will print this description in the error logs.
*   ***errors.expected***: A list of regular expressions, that will be expected to be in the error
    log of the validator. This field can be empty or omitted, in which case no errors will be
    expected.
*   ***errors.count***: An integer of the total amount of errors that is to be expected. Sometimes
    an error is repeated N times, and it's good practice to precisely establish how many errors
    should be expected. That said, this field can be empty or omitted.

## Reconsiling

The second important task of this utility is to take the wellformed (validated) configuration and
apply it to the VPP dataplane. The overall flow is this:

1. Prune phase (things in VPP that are not in the config), the order is:
   1.  Retrieve all LCP interfaces from VPP
       *   Starting with QinQ/QinAD, then Dot1Q/Dot1AD, then (BondEthernets, Tunnels, PHYs)
           *   Remove those that do not exist in the config
           *   Remove those that do exist in the config but are on a different phy
           *   Remove those that do exist in the config but have a different encapsulation
   1.  Retrieve all Loopbacks and BVIs from VPP
       *   Remove those that do not exist in the config
       *   Remove all IP addresses that are not in the config
   1.  Retrieve all Bridge Domains from VPP
       *   Remove those that do not exist in the config
       *   Remove all IP addresses that are not in the config
       *   Remove all member interfaces that are not in the config, return them to L3 mode
       *   Remove tag-rewrite options on member interfaces if they have encapsulation
   1.  For L2 Cross Connects from VPP
       *   For interfaces that do not exist in the config (either as source or target):
           *   Return the interface to L3 mode
           *   Remove tag-rewrite options on if it has encapsulation
   1.  Retrieve all BondEthernets from VPP
       *   Remove those that do not exist in the config
       *   Remove all member interfaces that are not in the config, return them to L3 mode
       *   Remove all IP addresses that are not in the config
   1.  Retrieve all Tunnels from VPP
       *   Remove those that do not exist in the config
       *   Remove all IP addresses that are not in the config
   1.  Retrieve all interfaces from VPP
       *   Starting with QinQ/QinAD, then Dot1Q/Dot1AD, then (BondEthernets, Tunnels):
           *   Remove those that do not exist in the config
           *   Remove those that do exist in the config but have a different encapsulation
           *   Remove all IP addresses that are not in the config
       *  And finally, for each PHY:
           *   Remove all IP addresses that are not in the config
           *   If not in the config, return to default (L3 mode, MTU 9000, admin-state down)
1. Create phase (things in the config that are not in VPP), the order is:
   1.  Loopbacks and BVIs
   1.  Bridge Domains
   1.  BondEthernets
   1.  Tunnels
   1.  Dot1Q and Dot1AD sub-interfaces
   1.  Qin1Q and Qin1AD sub-interfaces
   1.  LCP pairs
1. Sync phase, for each interface in the configuration
   1.  For BondEthernets:
       *   Set MTU of member interfaces
       *   Add them as slaves, lexicographically sorted by name
       *   Set their admin-state up
       *   Ensure LCP has the same MAC as the BondEthernet
   1.  For Bridge Domains:
       *   Set the MTU of the member interface (including BVI)
       *   Add the members (including the BVI)
       *   Set tag-rewrite options if any of the interfaces have encapsulation
   1.  For L2 Cross Connects, if applicable:
       *   Set the MTU of the two interfaces
       *   Set the L2XC option on both
       *   Set tag-rewrite options if any of the interfaces have encapsulation
   1.  Decrease MTU for QinQ/QinAD, then Dot1Q/Dot1AD, then (BondEthernets, Tunnels, PHYs)
   1.  Raise MTU for (PHYs, Tunnels, BondEthernets), then Dot1Q/Dot1AD, then QinQ/QinAD
   1.  Add IPv4/IPv6 addresses
   1.  Set admin state up
