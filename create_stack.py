# /usr/bin/env python

"""Create stack from cloud formation template.

Usage:
    create_stack.py [-v] -f CONFIGURATION_FILE ENV

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
    stack = conn.create_stack(stack_name=stack_name, template_url=template_url,
                              parameters=[("MaxSize", "1"), ("MinSize", "1")], tags={"name": stack_name})
    next_token = ""
    status = ""
    while "COMPLETE" not in status:
        status = conn.describe_stacks(stack_name_or_id=stack_name)[0].stack_status
        for event in conn.describe_stack_events(stack_name, next_token):
            next_token = event.event_id
            print event
        time.sleep(5)
