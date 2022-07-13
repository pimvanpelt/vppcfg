VERSION=0.0.1
VPPCFG:=vppcfg
PYTHON?=python3
PIP?=pip
PIP_DEPENDS=build yamale netaddr pylint
PIP_DEPENDS+=argparse pyyaml ipaddress black
WIPE=dist $(VPPCFG).egg-info .pybuild debian/vppcfg debian/vppcfg.*.log
WIPE+=debian/vppcfg.*.debhelper debian/.debhelper debian/files
WIPE+=debian/vppcfg.substvars
WHL_INSTALL=dist/$(VPPCFG)-$(VERSION)-py3-none-any.whl
TESTS=$(VPPCFG)/tests.py

.PHONY: build
build:
	$(PYTHON) -m build

.PHONY: install-deps
install-deps:
	sudo $(PIP) install $(PIP_DEPENDS)

.PHONY: install
install:
	sudo $(PIP) install $(WHL_INSTALL)

.PHONY: pkg-deb
pkg-deb:
	dpkg-buildpackage -uc -us -b

.PHONY: check-style
check-style:
	PYTHONPATH=./$(VPPCFG) pylint ./$(VPPCFG)

.PHONY: test
test:
	PYTHONPATH=./$(VPPCFG) $(PYTHON) $(TESTS)

.PHONY: uninstall
uninstall:
	sudo $(PIP) uninstall $(VPPCFG)

.PHONY: wipe
wipe:
	$(RM) -rf $(WIPE)
