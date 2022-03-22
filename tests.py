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

import sys
import yaml
from validator import Validator
import glob
import re
import unittest

try:
    import argparse
except ImportError:
    print("ERROR: install argparse manually: sudo pip install argparse")
    sys.exit(-2)


class YAMLTest(unittest.TestCase):
    def __init__(self, testName, yaml_filename, yaml_schema):
        # calling the super class init varies for different python versions.  This works for 2.7
        super(YAMLTest, self).__init__(testName)
        self.yaml_filename = yaml_filename
        self.yaml_schema = yaml_schema

    def test_yaml(self):
        unittest = None
        cfg = None
        n=0
        try:
            with open(self.yaml_filename, "r") as f:
                for data in yaml.load_all(f, Loader=yaml.Loader):
                    if n==0:
                        unittest = data
                        n = n + 1
                    elif n==1:
                        cfg = data
                        n = n + 1
        except:
            pass
        self.assertEqual(n,2)
        self.assertIsNotNone(unittest)
        if not cfg:
            return

        v = Validator(schema=self.yaml_schema)
        rv, msgs = v.validate(cfg)

        msgs_unexpected = 0
        msgs_expected = []
        if 'test' in unittest and 'errors' in unittest['test'] and 'expected' in unittest['test']['errors']:
            msgs_expected = unittest['test']['errors']['expected']

        fail = False
        for m in msgs:
            this_msg_expected = False
            for expected in msgs_expected:
                if re.match(expected, m):
                    this_msg_expected = True
                    break
            if not this_msg_expected:
                print("%s: Unexpected message: %s" % (self.yaml_filename, m), file=sys.stderr)
                fail = True

        count = 0
        if 'test' in unittest and 'errors' in unittest['test'] and 'count' in unittest['test']['errors']:
            count = unittest['test']['errors']['count']

        self.assertEqual(len(msgs), count)
        self.assertFalse(fail)

        return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-t', '--test', dest='test', type=str, nargs='+', default=['unittest/yaml/*.yaml'], help="""YAML test file(s)""")
    parser.add_argument('-s', '--schema', dest='schema', type=str, default='./schema.yaml', help="""YAML schema validation file""")
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help="""Enable debug, default False""")
    parser.add_argument('-q', '--quiet', dest='quiet', action='store_true', help="""Be quiet (only log warnings/errors), default False""")


    args = parser.parse_args()
    if args.debug:
        verbosity=2
    elif args.quiet:
        verbosity=0
    else:
        verbosity=1
    yaml_suite = unittest.TestSuite()
    for pattern in args.test:
        for fn in glob.glob(pattern):
            yaml_suite.addTest(YAMLTest('test_yaml', yaml_filename=fn, yaml_schema=args.schema))
    yaml_ok = unittest.TextTestRunner(verbosity=verbosity, buffer=True).run(yaml_suite)

    tests = unittest.TestLoader().discover(start_dir=".", pattern='test_*.py')
    unit_ok = unittest.TextTestRunner(verbosity=verbosity, buffer=True).run(tests).wasSuccessful()

    if not yaml_ok or not unit_ok:
        sys.exit(-1)
    sys.exit(0)
