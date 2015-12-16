# /usr/bin/env python

"""MarkLogic CloudFormation template generator.

Usage:
    ml_stack.py [-v] -f CONFIGURATION_FILE ENV

Options:
    -f <file> cluster configuration file
"""
from docopt import docopt
from troposphere import Ref, Template, Parameter, GetAtt
import troposphere.ec2 as ec2
import troposphere.elasticloadbalancing as elb
import troposphere.autoscaling as autoscaling
import json
import logging
from troposphere import Base64, Join
import boto


def get_name_prefix(env, config):
    return env + config["Type"] + config["Component"]

def create_name(base, az, instanceNumber, env, config):
    return get_name_prefix(env, config) + base + az + str(instanceNumber)


def get_private_subnet_id(aws_config, az):
    return get_private_subnets(aws_config)["Sandbox_DEV_PVT_1" + az]


def get_private_subnets(aws_config):
    return aws_config["Subnets"]["Sandbox_DEV"]["PrivateSubnets"]


def create_key_value_tags(config, base, az, instanceNumber, env):
    tags = []
    tags.append(ec2.Tag("name", get_name_prefix(env, config) + "-" + base + "-zone-" + az + "-instance-" + str(instanceNumber)))
    tags.append(ec2.Tag("env", env))
    tags.append(ec2.Tag("componentType", config["Type"]))
    tags.append(ec2.Tag("component", config["Component"]))
    tags.append(ec2.Tag("zone", az))
    tags.append(ec2.Tag("instance", str(instanceNumber)))
    tags.append(ec2.Tag("type", base))
    return tags


def create_autoscalling_tags(config, base, az, instanceNumber, env):
    tags = []
    tags.append(autoscaling.Tag("name", get_name_prefix(env, config) + "-" + base + "-zone-" + az + "-instance-" + str(instanceNumber), True))
    return tags


def create_launch_config(aws_config, config, instance_type, az, instance_number, security_groups, env):
    launch_configuration = autoscaling.LaunchConfiguration(create_lauch_config_name(az, instance_number, env, config))
    launch_configuration.EbsOptimized = config["EbsOptimized"]
    launch_configuration.IamInstanceProfile = config["IamInstanceProfile"]
    launch_configuration.ImageId = config["MarkLogicAMIImageId"]
    launch_configuration.InstanceType = Ref(instance_type)
    launch_configuration.KeyName = config["KeyName"]
    security_group_list = []
    for group in security_groups:
        security_group_list.append(Ref(group))

    launch_configuration.SecurityGroups = security_group_list
    instance_config = {"stack-name": get_name_prefix(env, config), "region": aws_config["Region"], "env": env, "componentType": config["Type"],
                       "component": config["Component"], "zone": az, "instanceNumber": instance_number,
                       "ConfigVolumes": config["ConfigVolumes"], "DataVolumes": config["DataVolumes"]}
    with open ("attach_volumes.py", "r") as attach_volumes_file:
        attach_volumes_file_string=attach_volumes_file.read()

    with open ("format_volumes.py", "r") as format_volumes_file:
        format_volumes_file_string=format_volumes_file.read()

    launch_configuration.UserData = Base64(Join('', [
        "#!/bin/bash\n",
        'echo \''+json.dumps(instance_config)+'\' > /etc/instance.conf\n',
        "echo \"INFO generated /etc/instance.conf\"\n",
        "mkdir -p /opt/custom-marklogic\n",
        'cat > /opt/custom-marklogic/attach_volumes.py <<EOF\n'+attach_volumes_file_string+'\nEOF\n',
        'cat > /opt/custom-marklogic/format_volumes.py <<EOF\n'+format_volumes_file_string+'\nEOF\n',
        'python /opt/custom-marklogic/attach_volumes.py'


    ]))
    return launch_configuration


def create_autoscalling_group(aws_config, config, az, instanceNumber, security_groups, load_balancers, min_size, max_size, env):
    auto_scaling_group = autoscaling.AutoScalingGroup(create_name("ASG", az, instanceNumber, env, config))
    auto_scaling_group.AvailabilityZones = [get_availability_zone(aws_config, az)]
    auto_scaling_group.LaunchConfigurationName = Ref(create_lauch_config_name(az, instanceNumber, env, config))
    load_balancer_list = []
    for load_balancer in load_balancers:
        load_balancer_list.append(Ref(load_balancer))
    auto_scaling_group.LoadBalancerNames = load_balancer_list
    auto_scaling_group.MaxSize = Ref(min_size)
    auto_scaling_group.MinSize = Ref(max_size)
    auto_scaling_group.Tags = create_autoscalling_tags(config, "ASG", az, instanceNumber, env)
    auto_scaling_group.VPCZoneIdentifier = [
        aws_config["Subnets"]["Sandbox_DEV"]["PrivateSubnets"]["Sandbox_DEV_PVT_1" + az]]
    return auto_scaling_group


def get_availability_zone(aws_config, az):
    return aws_config["Region"] + az


def create_lauch_config_name(az, instanceNumber, env, config):
    return create_name("LC", az, instanceNumber, env, config)


def create_instance(aws_config, config, az, instanceNumber, env):
    instance = ec2.Instance(create_name("Instance", az, instanceNumber, env, config))
    instance.AvailabilityZone = get_availability_zone(aws_config, az)
    instance.EbsOptimized = config["EbsOptimized"]
    instance.ImageId = config["MarkLogicAMIImageId"]
    instance.InstanceType = config["InstanceType"]
    instance.SubnetId = get_private_subnet_id(aws_config, az)
    instance.Tags = create_key_value_tags(config, "instance", az, instanceNumber)
    instance.Tenancy = config["Tenancy"]
    return instance


def create_network_interface(aws_config, config, az, instanceNumber, group_set, env):
    network_interface = ec2.NetworkInterface(create_name("ENI", az, instanceNumber, env, config))
    network_interface.Description = "For MarkLogic zone " + az + " instance " + str(instanceNumber)
    group_set_list = []
    for group in group_set:
        group_set_list.append(Ref(group))
    network_interface.GroupSet = group_set_list
    network_interface.SubnetId = get_private_subnet_id(aws_config, az)
    network_interface.Tags = create_key_value_tags(config, "NetworkInterface", az, instanceNumber, env)
    return network_interface


def create_data_volume(aws_config, config, az, instanceNumber, data_volume_number, env):
    data_volume = ec2.Volume(create_name("DataVolume", az, instanceNumber, env, config))
    data_volume.AvailabilityZone = get_availability_zone(aws_config, az)
    data_volume_config = config["DataVolumes"][data_volume_number - 1]
    data_volume.Encrypted = data_volume_config["Encrypted"]
    if data_volume_config["VolumeType"] != "gp2":
        data_volume.Iops = data_volume_config["Iops"]
    data_volume.Size = data_volume_config["Size"]
    tags = create_key_value_tags(config, "DataVolume", az, instanceNumber, env)
    tags.append(ec2.Tag("volume", data_volume_number))
    tags.append(ec2.Tag("Device", data_volume_config["Device"]))
    tags.append(ec2.Tag("MountDirectory", data_volume_config["MountDirectory"]))
    data_volume.Tags = tags
    data_volume.VolumeType = data_volume_config["VolumeType"]
    if data_volume_config["FromSnapshot"] == "true":
        data_volume.SnapshotId = data_volume_config["SnapshotId"]
    return data_volume


def create_config_volume(aws_config, config, az, instance_number, config_volume_number, env):
    config_volume = ec2.Volume(create_name("ConfigVolume", az, instance_number, env, config))
    config_volume.AvailabilityZone = get_availability_zone(aws_config, az)
    config_volume_config = config["ConfigVolumes"][config_volume_number - 1]
    config_volume.Encrypted = config_volume_config["Encrypted"]
    if config_volume_config["VolumeType"] != "gp2":
        config_volume.Iops = config_volume_config["Iops"]
    config_volume.Size = config_volume_config["Size"]
    tags = create_key_value_tags(config, "ConfigVolume", az, instance_number, env)
    tags.append(ec2.Tag("volume", config_volume_number))
    tags.append(ec2.Tag("Device", config_volume_config["Device"]))
    tags.append(ec2.Tag("MountDirectory", config_volume_config["MountDirectory"]))
    config_volume.Tags = tags
    config_volume.VolumeType = config_volume_config["VolumeType"]
    if config_volume_config["FromSnapshot"] == "true":
        config_volume.SnapshotId = config_volume_config["SnapshotId"]
    return config_volume


def create_load_balancer_security_group(aws_config, config, env):
    return ec2.SecurityGroup(
        get_load_balancer_security_group_logical_name(env, config),
        GroupDescription="Enable HTTP/XDBC access on the inbound port",
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort=config["LoadBalancedPorts"]["FromPort"],
                ToPort=config["LoadBalancedPorts"]["ToPort"],
                CidrIp=aws_config["VpcCidrIp"],
            )
        ],
        VpcId=aws_config["VpcId"]
    )


def get_load_balancer_security_group_logical_name(env, config):
    return get_name_prefix(env, config) + "LBSG"


def create_cluster_security_group(aws_config, config, load_balancer_security_group, env):
    return ec2.SecurityGroup(
        get_name_prefix(env, config)+"InternalSG",
        GroupDescription="Enable communication of cluster ports e.g. For nodes within cluster and replication between clusters.",
        SecurityGroupIngress=[
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort=config["ClusterPorts"]["FromPort"],
                ToPort=config["ClusterPorts"]["ToPort"],
                CidrIp=aws_config["VpcCidrIp"],
            ),
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort="22",
                ToPort="22",
                CidrIp=aws_config["VpcCidrIp"],
            ),
            ec2.SecurityGroupRule(
                IpProtocol="tcp",
                FromPort=config["LoadBalancedPorts"]["FromPort"],
                ToPort=config["LoadBalancedPorts"]["ToPort"],
                SourceSecurityGroupId= GetAtt(get_load_balancer_security_group_logical_name(env, config), "GroupId")
            )
        ],
        VpcId=aws_config["VpcId"]
    )


def create_load_balancer(aws_config, config, security_groups, env):
    load_balancer = elb.LoadBalancer(get_name_prefix(env, config)+"ELB")
    config_load_balancer = config["LoadBalancer"]
    access_logging_policy = config_load_balancer["AccessLoggingPolicy"]
    load_balancer.AccessLoggingPolicy = elb.AccessLoggingPolicy(
        EmitInterval=access_logging_policy["EmitInterval"],
        Enabled=access_logging_policy["Enabled"] == "true",
        S3BucketName=access_logging_policy["S3BucketName"],
        S3BucketPrefix=access_logging_policy["S3BucketPrefix"]
    )
    load_balancer.AppCookieStickinessPolicy = config_load_balancer["AppCookieStickinessPolicy"]
    draining_policy = config_load_balancer["ConnectionDrainingPolicy"]
    load_balancer.ConnectionDrainingPolicy = elb.ConnectionDrainingPolicy(
        Enabled=bool(draining_policy["Enabled"]),
        Timeout=draining_policy["Timeout"]
    )
    load_balancer.CrossZone = config_load_balancer["CrossZone"]
    health_check = config_load_balancer["HealthCheck"]
    load_balancer.HealthCheck = elb.HealthCheck(
        Target=health_check["Target"],
        HealthyThreshold=health_check["HealthyThreshold"],
        UnhealthyThreshold=health_check["UnhealthyThreshold"],
        Interval=health_check["Interval"],
        Timeout=health_check["Timeout"]
    )
    load_balancer.Listeners = config_load_balancer["Listeners"]
    load_balancer.Scheme = config_load_balancer["Scheme"]
    load_balancer.Subnets = get_private_subnets(aws_config).values()
    security_groups_list = []
    for group in security_groups:
        security_groups_list.append(Ref(group))

    load_balancer.SecurityGroups = security_groups_list
    load_balancer.Tags = create_key_value_tags(config, "LoadBalancer", "allzones", None, env)
    return load_balancer


if __name__ == '__main__':
    arguments = docopt(__doc__)

    if arguments['-v']:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    env = arguments["ENV"].lower()

    with open('conf/aws_config.json') as aws_config_file:
        aws_config = json.load(aws_config_file)

    with open(arguments["-f"]) as config_file:
        config = json.load(config_file)

    vpc = {
        "VpcId": aws_config["VpcId"]
    }

    zones = config.get("Zones", aws_config["Zones"])

    template = Template()
    template.add_version("2010-09-09")

    min_size = Parameter(
        "MinSize",
        Default="1",
        AllowedValues=["0", "1"],
        Type="Number",
        Description="Set MinSize and MaxSize to 0 to stop instances. Set it to 1 to start instances",
    )
    template.add_parameter(min_size)

    max_size = Parameter(
        "MaxSize",
        Default="1",
        AllowedValues=["0", "1"],
        Type="Number",
        Description="Set MinSize and MaxSize to 0 to stop instances. Set it to 1 to start instances.",
    )
    template.add_parameter(max_size)

    instance_type = Parameter(
        "InstanceType",
        Default="t2.small",
        AllowedValues=["t2.micro", "t2.small", "t2.medium", "t2.large", "m4.large", "m4.xlarge", "m4.2xlarge", "m4.4xlarge", "m4.10xlarge", "m3.medium", "m3.large", "m3.xlarge", "m3.2xlarge", "c4.large", "c4.xlarge", "c4.2xlarge", "c4.4xlarge", "c4.8xlarge", "c3.large", "c3.xlarge", "c3.2xlarge", "c3.4xlarge", "c3.8xlarge", "r3.large", "r3.xlarge", "r3.2xlarge", "r3.4xlarge", "r3.8xlarge", "i2.xlarge", "i2.2xlarge", "i2.4xlarge", "i2.8xlarge", "d2.xlarge", "d2.2xlarge", "d2.4xlarge", "d2.8xlarge", "g2.2xlarge", "g2.8xlarge"],
        Type="String",
        Description="Set type of EC2 instance to launch.",
    )
    template.add_parameter(instance_type)


    load_balancer_security_group = create_load_balancer_security_group(aws_config, config, env)
    template.add_resource(load_balancer_security_group)
    load_balancer = create_load_balancer(aws_config, config, [load_balancer_security_group], env)
    template.add_resource(load_balancer)

    cluster_security_group = create_cluster_security_group(aws_config, config, load_balancer_security_group, env)
    template.add_resource(cluster_security_group)


    for az in zones:
        for instance_number in range(1, config["NumberOfInstancesPerZone"] + 1):
            launch_config = create_launch_config(aws_config, config, instance_type, az, instance_number, [cluster_security_group], env)
            template.add_resource(launch_config)
            autoscalling_group = create_autoscalling_group(aws_config, config, az, instance_number,
                                                           [cluster_security_group], [load_balancer], min_size, max_size, env)
            template.add_resource(autoscalling_group)
            for config_volume_number in range(1, len(config["ConfigVolumes"]) + 1):
                config_volume = create_config_volume(aws_config, config, az, instance_number, config_volume_number, env)
                template.add_resource(config_volume)
            for data_volume_number in range(1, len(config["DataVolumes"])+1):
                data_volume = create_data_volume(aws_config, config, az, instance_number, data_volume_number, env)
                template.add_resource(data_volume)
            network_interface = create_network_interface(aws_config, config, az, instance_number,
                                                         [cluster_security_group], env)
            template.add_resource(network_interface)

    print(template.to_json())

    template_file_name =  env + config["Type"] + config["Component"] + ".json"
    template_file_path = 'templates/' + template_file_name
    with open(template_file_path, 'w') as template_file:
        template_file.write(template.to_json())

    s3_connection = boto.connect_s3()
    bucket = s3_connection.get_bucket(aws_config["S3BucketForTemplates"])
    key = boto.s3.key.Key(bucket, aws_config["S3TemplatesKeyPrefix"]+template_file_name)
    with open(template_file_path) as f:
        key.set_contents_from_file(f)
