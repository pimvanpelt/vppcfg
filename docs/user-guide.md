# A VPP Configuration Utility

`vppcfg` is a commandline utility that applies a YAML based configuration file
safely to a running VPP dataplane. It contains a strict syntax and semantic validation,
and a path planner that brings the dataplane from any configuration state safely to any
other configuration state, as defined by these YAML files.

## User Guide

```
usage: vppcfg [-h] [-d] [-q] [-f] {check,dump,plan,apply} ...

positional arguments:
  {check,dump,plan,apply}
    check               check given YAML config for validity (no VPP)
    dump                dump current running VPP configuration (VPP readonly)
    plan                plan changes from current VPP dataplane to target config (VPP readonly)
    apply               apply changes from current VPP dataplane to target config

optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           enable debug logging, default False
  -q, --quiet           be quiet (only warnings/errors), default False
  -f, --force           force progress despite warnings, default False
```

### vppcfg check

The purpose of the **check** module is to read a YAML configuration file and validate
its syntax (using Yamale) and its semantics (using vppcfg's constraints based system).
If the config file is valid, the return value will be 0. If any syntax errors or semantic
constraint violations are found, the return value will be non-zero.

The configuration file (in YAML format) is given by a mandatory `-c/--config` flag, and
optionally a Yamale schema file, given by the `-s/--schema` flag (which will default to
the built-in default schema). Any violations will be shown in the ERROR log. A succesful
run will look like this:

```
$ ./vppcfg check -c example.yaml && echo OK
[INFO    ] root.main: Loading configfile example.yaml
[INFO    ] vppcfg.config.valid_config: Configuration validated successfully
[INFO    ] root.main: Configuration is valid
OK

$ echo $?
0
```

A failure to validate can be due to one of two main reasons. Firstly, syntax violations
that trip the syntax parser, which can be seen in the output with the tag `yamale:`:

```
$ cat yamale-invalid.yaml 
interfaces:
  GigabitEthernet1/0/0:
    descr: "the proper field name is description"
    mtu: 127

$ ./vppcfg check -c yamale-invalid.yaml && echo OK
[INFO    ] root.main: Loading configfile yamale-invalid.yaml
[ERROR   ] vppcfg.config.valid_config: yamale: interfaces.GigabitEthernet1/0/0.descr: Unexpected element
[ERROR   ] vppcfg.config.valid_config: yamale: interfaces.GigabitEthernet1/0/0.mtu: 127 is less than 128
[ERROR   ] root.main: Configuration is not valid, bailing
```

Some configurations may be syntactically correct but still can't be applied, because they
might break some constraint or requirement from VPP. For example, an interface that has an
IP address can't be a member in a bridgedomain, or a sub-interface that has an IP address
with an incompatible encapsulation (notably, the lack of `exact-match`).

Semantic violations are mostly self-explanatory, just be aware that one YAML configuration
error may trip multiple validators:

```
$ cat semantic-invalid.yaml
interfaces:
  GigabitEthernet3/0/0:
    sub-interfaces:
      100:
        addresses: [ 192.0.2.1/30 ]
        encapsulation:
          dot1q: 100
  GigabitEthernet3/0/1:
    mtu: 1500
    addresses: [ 10.0.0.1/29 ]

bridgedomains:
  bd1:
    mtu: 9000
    interfaces: [ GigabitEthernet3/0/1 ]

$ ./vppcfg check -c semantic-invalid.yaml && echo OK
[INFO    ] root.main: Loading configfile semantic-invalid.yaml
[ERROR   ] vppcfg.config.valid_config: sub-interface GigabitEthernet3/0/0.100 has an address but its encapsulation is not exact-match
[ERROR   ] vppcfg.config.valid_config: interface GigabitEthernet3/0/1 is in L2 mode but has an address
[ERROR   ] vppcfg.config.valid_config: bridgedomain bd1 member GigabitEthernet3/0/1 has an address
[ERROR   ] vppcfg.config.valid_config: bridgedomain bd1 member GigabitEthernet3/0/1 has MTU 1500, while bridge has 9000
[ERROR   ] root.main: Configuration is not valid, bailing
```

In general, it's good practice to check the validity of a YAML file before attempting to
offer it for reconciliation. `vppcfg` will make no guarantees in case its input is not
fully valid!

### vppcfg dump

### vppcfg plan

### vppcfg apply
