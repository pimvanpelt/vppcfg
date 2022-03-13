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
