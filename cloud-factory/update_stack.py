# /usr/bin/env python

"""Update stack from cloud formation template.

Usage:
    update_stack.py [-v] -f CONFIGURATION_FILE ENV

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

    template_url = "https://s3.amazonaws.com/"+aws_config["S3BucketForTemplates"]+aws_config["S3TemplatesKeyPrefix"]+stack_name+".json"
    stack = conn.update_stack(stack_name=stack_name, template_url=template_url,
                                  parameters=[("MaxSize", "1"), ("MinSize", "1")], tags={"name": stack_name})
    next_token = 0
    status = ""
    while "COMPLETE" not in status:
        describe_stacks = conn.describe_stacks(stack_name_or_id=stack_name)
        status = describe_stacks[0].stack_status
        events = conn.describe_stack_events(stack_name, next_token)
        for event in events:
            print event
        next_token = events.next_token
        time.sleep(5)
