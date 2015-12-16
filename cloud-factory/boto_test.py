import boto

"""
conn = boto.connect_s3()

for b in conn.get_all_buckets():
    print b.name
    """
conn = boto.connect_ec2()
config_volumes = conn.get_all_volumes(None,
                                          filters={"tag:stack-name": "rasingh-MarkLogic"})

network_interfaces = conn.get_all_network_interfaces(None, filters={
    "tag:aws:cloudformation:stack-name": "rasinghMarkLogicCluster01"})

for network_interface in network_interfaces:
    print "%s %s" % (network_interface.private_ip_address, network_interface.availability_zone)

instances = conn.get_all_instances(filters={"tag:Name": "rasingh-MarkLogic"})
print config_volumes

"""
10.221.156.252 us-east-1e
10.221.129.243 us-east-1e
10.221.66.196 us-east-1c
10.221.73.249 us-east-1c
10.221.15.153 us-east-1b
10.221.16.180 us-east-1b
"""