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
## Install python build dependencies 
$ make install-deps

## Ensure all unittests pass.
$ make test

## Build vppcfg
$ make build

## Install the tool with PIP
$ make install

## To build & install debian packaging
$ make pkg-deb
$ ls -l ../vppcfg_*_amd64.deb
```

## Running

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

Please see vppcfg <command> -h   for per-command arguments
```

## Documentation

Main user-focused documentation:
*   [YAML Configuration Guide](docs/config-guide.md)
*   [User Guide](docs/user-guide.md)

Developer deep-dives:
*   [Validation](https://ipng.ch/s/articles/2022/03/27/vppcfg-1.html)
*   [Path Planning](https://ipng.ch/s/articles/2022/04/02/vppcfg-2.html)
*   [Design - Reconciliation](docs/design.md)


## Licensing

The code in this project is release under Apache 2.0 license. A copy of the license
is provided in this repo [here](LICENSE). All contributions are held against our
[contributing](docs/contributing.md) guidelines. Notably, all code must be licensed
Apache 2.0, and all contributions must come with a certificate of origin in the
form of a `Signed-off-by` field in the commit.

All documentation under the docs/ directory is licensed Creative Commons Attribution
4.0 International License ([details](http://creativecommons.org/licenses/by/4.0/)). A
copy of the license is provided in this repo [here](docs/LICENSE).
