# /usr/bin/env python

"""Delete cloud formation stack.

Usage:
    delete_stack.py [-v] -f CONFIGURATION_FILE ENV

Options:
    -f <file> cluster configuration file
"""

import boto
import time
from docopt import docopt
import logging
import json

def get_name_prefix():
    return env + config["Type"] + config["Component"]

if __name__ == '__main__':
    arguments = docopt(__doc__)

    env = arguments["ENV"].lower()

    with open('conf/aws_config.json') as aws_config_file:
        aws_config = json.load(aws_config_file)

    with open(arguments["-f"]) as config_file:
        config = json.load(config_file)


    conn = boto.connect_cloudformation()
    stack_name = get_name_prefix()

    stack = conn.delete_stack(stack_name)
    next_token = ""
    status = ""

    while "COMPLETE" not in status:
        try:
            status = conn.describe_stacks(stack_name_or_id=stack_name)[0].stack_status
            for  event in conn.describe_stack_events(stack_name, next_token):
                next_token = event.event_id
                print event
            time.sleep(5)
        except boto.exception.BotoServerError as e:
            print(e)
            status = "COMPLETE"

