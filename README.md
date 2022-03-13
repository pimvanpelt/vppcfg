# A VPP Configuration Utility

This tool reads a configuration file, checks it for syntax and semantic correctness, and then
reconciles a running [VPP](https://fd.io/) daemon with its configuration. It is meant to be
re-entrant and stateless. The tool connects to the VPP API and creates/removes all of the
configuration in a minimally intrusive way.

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

