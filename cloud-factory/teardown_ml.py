#!/usr/bin/env python

"""Teardown MarkLogic cluster.

Usage:
  teardown_ml.py [-v] -f CONFIGURATION_FILE ENV

Options:
    -f <file> cluster configuration file
"""

import os, sys

from docopt import docopt
from pexpect import pxssh
import setup_ml
import logging
import json

if __name__ == '__main__':
    arguments = docopt(__doc__, version="0.1")

    if arguments['-v']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    env = arguments["ENV"].lower()

    with open('conf/aws_config.json') as aws_config_file:
        aws_config = json.load(aws_config_file)

    with open(arguments["-f"]) as config_file:
        config = json.load(config_file)

    hosts = [setup_ml.get_permanent_ip(instance) for instance in setup_ml.find_instances(env, config)]

    for host in hosts:
      s = pxssh.pxssh()
      s.login(host, os.environ['LOGNAME'])
      s.sendline('uptime')
      s.prompt()
      s.sendline("sudo service MarkLogic stop")
      s.prompt()
      print(s.before)
      s.sendline("sudo rm -rf /var/opt/MarkLogic")
      s.prompt()
      print(s.before)
      s.sendline("sudo service MarkLogic start")
      s.prompt()
      print(s.before)
      s.logout()

