import boto

"""
conn = boto.connect_s3()

for b in conn.get_all_buckets():
    print b.name
    """
conn = boto.connect_ec2()
config_volumes = conn.get_all_volumes(None,
                                          filters={"tag:stack-name": "rasingh-MarkLogic"})
instances = conn.get_all_instances(filters={"tag:Name": "rasingh-MarkLogic"})
print config_volumes