# /usr/bin/env python

"""MarkLogic CloudFormation template generator.

Usage:
    create_stack.py [-v] [-f CLOUD_FORMATION_TEMPLATE_FILE]

Options:
    -f CONFIGURATION_FILE       MarkLogic cluster Configuration file [default: conf/ml_master.json]
"""

import boto

if __name__ == '__main__':

    conn = boto.connect_cloudformation()
    master = "rasingh-MarkLogic-ml-master"
    with open ("templates/ml-master.json", "r") as myfile:
        template=myfile.read()
        stack = conn.create_stack(stack_name=master, template_body=template,
                                  parameters=[("MaxSize", "1"), ("MinSize", "1")], tags={"name": master})
        for event in conn.describe_stack_events(master):
            print event
