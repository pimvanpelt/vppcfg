#!/usr/bin/env python3
#
# Copyright (c) 2022 Pim van Pelt
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# -*- coding: utf-8 -*-
""" This is a unit test suite for vppcfg """
# pylint: disable=duplicate-code
import os
import sys
import glob
import re
import unittest
import yaml

try:
    from vppcfg.config import Validator
except ModuleNotFoundError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from vppcfg.config import Validator

try:
    import argparse
except ImportError:
    print("ERROR: install argparse manually: sudo pip install argparse")
    sys.exit(-2)


def example_validator(_yaml):
    """A simple example validator that takes the YAML configuration file as an input,
    and returns a tuple of rv (return value, True is success), and a list of string
    messages to the validation framework."""
    return True, []


class YAMLTest(unittest.TestCase):
    """This test suite takes a YAML configuration file and holds it against the syntax
    (Yamale) and semantic validators, returning errors in case of validation failures.
    """

    def __init__(self, testName, yaml_filename, yaml_schema):
        # calling the super class init varies for different python versions.  This works for 2.7
        super().__init__(testName)
        self.yaml_filename = yaml_filename
        self.yaml_schema = yaml_schema

    def test_yaml(self):
        """The test executor"""
        test = None
        cfg = None
        ncount = 0
        with open(self.yaml_filename, "r", encoding="utf-8") as file:
            for data in yaml.load_all(file, Loader=yaml.Loader):
                if ncount == 0:
                    test = data
                    ncount += 1
                elif ncount == 1:
                    cfg = data
                    ncount += 1
        self.assertEqual(ncount, 2)
        self.assertIsNotNone(test)
        if not cfg:
            return

        validator = Validator(schema=self.yaml_schema)
        _rv, msgs = validator.validate(cfg)

        msgs_expected = []
        if (
            "test" in test
            and "errors" in test["test"]
            and "expected" in test["test"]["errors"]
        ):
            msgs_expected = test["test"]["errors"]["expected"]

        fail = False
        for msg in msgs:
            this_msg_expected = False
            for expected in msgs_expected:
                if re.match(expected, msg):
                    this_msg_expected = True
                    break
            if not this_msg_expected:
                print(
                    f"{self.yaml_filename}: Unexpected message: {msg}", file=sys.stderr
                )
                fail = True

        count = 0
        if (
            "test" in test
            and "errors" in test["test"]
            and "count" in test["test"]["errors"]
        ):
            count = test["test"]["errors"]["count"]

        if len(msgs) != count:
            print(
                f"{self.yaml_filename}: Unexpected error count {len(msgs)} (expecting {int(count)})",
                file=sys.stderr,
            )
        self.assertEqual(len(msgs), count)
        self.assertFalse(fail)

        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-t",
        "--test",
        dest="test",
        type=str,
        nargs="+",
        default=["unittest/yaml/*.yaml"],
        help="""YAML test file(s)""",
    )
    parser.add_argument(
        "-s",
        "--schema",
        dest="schema",
        type=str,
        default="./schema.yaml",
        help="""YAML schema validation file""",
    )
    parser.add_argument(
        "-d",
        "--debug",
        dest="debug",
        action="store_true",
        help="""Enable debug, default False""",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        dest="quiet",
        action="store_true",
        help="""Be quiet (only log warnings/errors), default False""",
    )

    args = parser.parse_args()
    if args.debug:
        VERBOSITY = 2
    elif args.quiet:
        VERBOSITY = 0
    else:
        VERBOSITY = 1
    yaml_suite = unittest.TestSuite()
    for pattern in args.test:
        for fn in glob.glob(pattern):
            yaml_suite.addTest(
                YAMLTest("test_yaml", yaml_filename=fn, yaml_schema=args.schema)
            )
    yaml_ok = (
        unittest.TextTestRunner(verbosity=VERBOSITY, buffer=True)
        .run(yaml_suite)
        .wasSuccessful()
    )

    tests = unittest.TestLoader().discover(start_dir=".", pattern="test_*.py")
    unit_ok = (
        unittest.TextTestRunner(verbosity=VERBOSITY, buffer=True)
        .run(tests)
        .wasSuccessful()
    )

    RETVAL = 0
    if not yaml_ok:
        RETVAL -= 1
    if not unit_ok:
        RETVAL -= 2
    sys.exit(RETVAL)
