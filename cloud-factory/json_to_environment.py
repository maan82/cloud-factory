#!/usr/bin/env python

# reads a json object as input and produces exports for shell environment

import json
import pipes
import sys

with open(sys.argv[1]) as env_file:
    for k, v in json.load(env_file).items():
        k = pipes.quote(k)
        v = pipes.quote(v)
        print "export %s=%s" % (k, v)