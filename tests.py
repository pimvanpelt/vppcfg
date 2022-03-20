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
import logging
from validator import Validator
import glob
import re
import unittest

try:
    import argparse
except ImportError:
    print("ERROR: install argparse manually: sudo pip install argparse")
    sys.exit(-2)


def yamltest_one(fn, schema):
    unittest = None
    cfg = None
    try:
        with open(fn, "r") as f:
            logging.debug("Reading test from %s" % fn)
            n=0
            for data in yaml.load_all(f, Loader=yaml.Loader):
                if n==0:
                    unittest = data
                    n = n + 1
                elif n==1:
                    cfg = data
                    n = n + 1
                else:
                    logging.error("Too many documents in %s" % fn)
                    return False
    except:
        logging.error("Couldn't read config from %s" % fn)
        return False

    logging.info("YAML %s" % fn)
    logging.debug("yamltest: %s" % unittest)
    logging.debug("config: %s" % cfg)
    this_failed =False
    v = Validator(schema=schema)
    rv, msgs = v.validate(cfg)
    try:
        if len(msgs) != unittest['test']['errors']['count']:
            logging.error("Unittest %s failed: expected %d error messages, got %d" % (fn, unittest['test']['errors']['count'], len(msgs)))
            this_failed = True
    except:
        pass

    msgs_unexpected = 0
    msgs_expected = []
    if 'test' in unittest and 'errors' in unittest['test'] and 'expected' in unittest['test']['errors']:
        msgs_expected = unittest['test']['errors']['expected']

    for m in msgs:
        this_msg_expected = False
        for expected in msgs_expected:
            logging.debug("Checking expected '%s'" % expected)
            if re.search(expected, m):
                logging.debug("Expected msg '%s' based on regexp '%s'" % (m, expected))
                this_msg_expected = True
                break
        if not this_msg_expected:
            logging.error("Unexpected message: %s" % (m))
            this_failed = True
    if this_failed:
        if 'test' in unittest and 'description' in unittest['test']:
            logging.error("YAML %s failed: %s" % (fn, unittest['test']['description']))
        else:
            logging.error("YAML %s failed" % (fn))
        return False
    else:
        logging.info("YAML %s passed" % (fn))
    return True


class YAMLTest(unittest.TestCase):
    def __init__(self, testName, yaml_filename, yaml_schema):
        # calling the super class init varies for different python versions.  This works for 2.7
        super(YAMLTest, self).__init__(testName)
        self.yaml_filename = yaml_filename
        self.yaml_schema = yaml_schema

    def test_yaml(self):
        print()
        assert yamltest_one(self.yaml_filename, self.yaml_schema)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-t', '--test', dest='test', type=str, nargs='+', default=['unittest/yaml/*.yaml'], help="""YAML test file(s)""")
    parser.add_argument('-s', '--schema', dest='schema', type=str, default='./schema.yaml', help="""YAML schema validation file""")
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help="""Enable debug, default False""")

    args = parser.parse_args()
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(format='[%(levelname)-8s] %(name)s.%(funcName)s: %(message)s', level=level)
    logging.debug("Arguments: %s" % args)

    yaml_suite = unittest.TestSuite()
    for pattern in args.test:
        for fn in glob.glob(pattern):
            yaml_suite.addTest(YAMLTest('test_yaml', yaml_filename=fn, yaml_schema=args.schema))
    yaml_ok = unittest.TextTestRunner(verbosity=2).run(yaml_suite)

    tests = unittest.TestLoader().discover(start_dir=".", pattern='test_*.py')
    unit_ok = unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful()

    if not yaml_ok or not unit_ok:
        sys.exit(-1)
    sys.exit(0)
