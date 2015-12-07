import boto

if __name__ == '__main__':
    conn = boto.connect_ec2()

    volumes = conn.get_all_volumes(None, filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master'})
    instances = conn.get_all_instances(None,
                                       filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master'})
    print volumes
    print instances
    """
    for instance in instances:
        volumes.
        instances[0].instances[0].tags["name"].split("-")
        volumes[0].tags["name"].split("-")

        [u'MarkLogic', u'loadbalancer', u'zone', u'e', u'instance', u'1']
        [u'MarkLogic', u'DataVolume', u'zone', u'c', u'instance', u'1']
    """