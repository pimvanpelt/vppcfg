VERSION=0.0.1
VPPCFG:=vppcfg
PYTHON?=python3
PIP?=pip
PIP_DEPENDS=build yamale netaddr pylint
PIP_DEPENDS+=argparse pyyaml ipaddress pyinstaller black
WHL_INSTALL=dist/$(VPPCFG)-$(VERSION)-py3-none-any.whl


.PHONY: build
build:
	$(PYTHON) -m build

.PHONY: install-deps
install-deps:
	sudo $(PIP) install $(PIP_DEPENDS)

.PHONY: install
install:
	sudo $(PIP) install $(WHL_INSTALL)

.PHONY: uninstall
uninstall:
	sudo $(PIP) uninstall $(VPPCFG)

.PHONY: wipe
wipe:
	$(RM) -rf dist $(VPPCFG).egg-info
