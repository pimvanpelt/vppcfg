#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import yaml
import logging
from validator import Validator
import glob
import re

try:
    import argparse
except ImportError:
    print("ERROR: install argparse manually: sudo pip install argparse")
    sys.exit(-2)


def load_unittest(fn):
    """ Read a two-document YAML file from 'fn', and expect the first document
    to be a unittest specification, and the second file to be a config file to
    be tested. Return them as a tuple, or [None, None] on error. """
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
                    return None, None
    except:
        logging.error("Couldn't read config from %s" % fn)
        return None, None
    return unittest, cfg


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-t', '--test', dest='test', type=str, nargs='+', default=['unittest/*.yaml'], help="""YAML test file(s)""")
    parser.add_argument('-s', '--schema', dest='schema', type=str, default='./schema.yaml', help="""YAML schema validation file""")
    parser.add_argument('-d', '--debug', dest='debug', action='store_true', help="""Enable debug, default False""")

    args = parser.parse_args()
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(format='[%(levelname)-8s] %(name)s.%(funcName)s: %(message)s', level=level)
    logging.debug("Arguments: %s" % args)

    errors = 0
    tests = 0
    for pattern in args.test:
        for fn in glob.glob(pattern):
            tests = tests + 1
            unittest, cfg = load_unittest(fn)
            if not unittest or not cfg:
                errors = errors + 1
                continue

            logging.info("Unittest %s" % fn)
            logging.debug("Unittest: %s" % unittest)
            logging.debug("Config: %s" % cfg)
            this_failed =False
            v = Validator(schema=args.schema)
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
                logging.error("Unittest %s failed" % (fn))
                errors = errors + 1
            else:
                logging.info("Unittest %s passed" % (fn))

    logging.info("Tests: %d run, %d failed" % (tests, errors))


if __name__ == "__main__":
    main()
