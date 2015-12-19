#!/usr/bin/env python

"""Teardown MarkLogic cluster.

Usage:
  teardown_ml.py [-v] -f CONFIGURATION_FILE ENV JUMP_SERVER

Options:
    -f <file> cluster configuration file
"""

from docopt import docopt
import setup_ml
import logging
import json
import commands
import time


def log(message):
    print "%s %s" % (time.strftime("[%d/%b/%Y:%H:%M:%S %z]"), message)


def print_command_output_status(command, status, output):
    log("INFO executed command : %s status : %s output : %s" % (command, status, output))


def run_command(command):
    status, output = commands.getstatusoutput(command)
    print_command_output_status(command, status, output)
    return (status, output)


def run_command_or_raise_exception(command):
    status, output = run_command(command)
    if status != 0:
        message = ("Error running command status : %s output : %s  for command : %s " % (status, output, command))
        raise Exception(message)


if __name__ == '__main__':
    arguments = docopt(__doc__, version="0.1")

    if arguments['-v']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    env = arguments["ENV"].lower()
    jump_server = arguments["JUMP_SERVER"].lower()

    with open('conf/aws_config.json') as aws_config_file:
        aws_config = json.load(aws_config_file)

    with open(arguments["-f"]) as config_file:
        config = json.load(config_file)

    hosts = [setup_ml.get_permanent_ip(instance) for instance in setup_ml.find_instances(env, config)]

    for host in hosts:
        print("Clearing host :  %s " % host)
        ssh_command_template = 'ssh -t -A -o StrictHostKeyChecking=no ec2-user@' + jump_server + ' "uptime && ssh -t -A -o StrictHostKeyChecking=no ec2-user@' + host + ' \'%s\' "'
        [run_command_or_raise_exception(command) for command in [(ssh_command_template % "sudo service MarkLogic stop"),
                                                                 (
                                                                 ssh_command_template % "sudo rm -rf /var/opt/MarkLogic/*"),
                                                                 (
                                                                 ssh_command_template % "sudo service MarkLogic start")]]
