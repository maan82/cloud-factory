# /usr/bin/env python

"""MarkLogic CloudFormation template generator.

Usage:
    update_stack.py [-v] [-f CLOUD_FORMATION_TEMPLATE_FILE]

Options:
    -f CONFIGURATION_FILE       MarkLogic cluster Configuration file [default: conf/ml_master.json]
"""

import boto
import time

if __name__ == '__main__':

    conn = boto.connect_cloudformation()
    master = "rasingh-MarkLogic-ml-master"
    with open ("templates/ml-master.json", "r") as myfile:
        template=myfile.read()
        stack = conn.update_stack(stack_name=master, template_body=template,
                                  parameters=[("MaxSize", "1"), ("MinSize", "1")], tags={"name": master})
    next_token = 0
    status = ""
    while "COMPLETE" not in status:
        status = conn.describe_stacks(stack_name_or_id=master)[0].stack_status
        events = conn.describe_stack_events(master, next_token)
        for event in events:
            print event
        next_token = events.next_token
        time.sleep(2)
