import unittest
import ml_stack

class TestMlStack(unittest.TestCase):
    aws_config = {
        "Region": "us-east-1",
        "Zones": ["b", "c", "e"],
        "VpcId": "vpc-6a80380e",
        "VpcCidrIp": "10.221.0.0/16",
        "Subnets": {
            "Sandbox_DEV": {
                "PublicSubnets": {
                    "Sandbox_DEV_PUB_1b": "subnet-6be5df40",
                    "Sandbox_DEV_PUB_1c": "subnet-7358a505",
                    "Sandbox_DEV_PUB_1e": "subnet-9b4ef1a6"
                },
                "PrivateSubnets": {
                    "Sandbox_DEV_PVT_1b": "subnet-c4e4deef",
                    "Sandbox_DEV_PVT_1c": "subnet-1558a563",
                    "Sandbox_DEV_PVT_1e": "subnet-e04ef1dd"
                }
            }
        },
        "S3BucketForTemplates": "sandbox-dev-bucket",
        "S3TemplatesKeyPrefix": "/rasingh/cloud-formation-templates/rasingh-MarkLogic/"
    }

    config = {
        "Type": "MarkLogic",
        "Component": "Cluster01",
        "MarkLogicAMIImageId": "ami-5bfcb131",
        "NumberOfInstancesPerZone": 1,
        "InstanceType": "t2.small",
        "EbsOptimized": "false",
        "IamInstanceProfile": "rasingh-MarkLogic-role",
        "KeyName": "rasingh-MarkLogic",
        "Tenancy": "default",
        "LoadBalancer": {
            "AccessLoggingPolicy": {
                "S3BucketName": "sandbox-dev-bucket",
                "S3BucketPrefix": "rasingh/load-balancer/475882391631/ml-master",
                "Enabled": "true",
                "EmitInterval": "5"
            },
            "AppCookieStickinessPolicy": [
                {
                    "CookieName": "SessionID",
                    "PolicyName": "MLSession"
                }
            ],
            "ConnectionDrainingPolicy": {
                "Enabled": "true",
                "Timeout": "60"
            },
            "CrossZone": "true",
            "Listeners": [
                {
                    "LoadBalancerPort": "9000",
                    "InstancePort": "9000",
                    "Protocol": "HTTP",
                    "PolicyNames": [
                        "MLSession"
                    ]
                },
                {
                    "LoadBalancerPort": "9001",
                    "InstancePort": "9001",
                    "Protocol": "HTTP",
                    "PolicyNames": [
                        "MLSession"
                    ]
                }
            ],
            "HealthCheck": {
                "Target": "HTTP:7997/",
                "HealthyThreshold": "3",
                "UnhealthyThreshold": "5",
                "Interval": "10",
                "Timeout": "5"
            },
            "Scheme": "internal"
        },
        "LoadBalancedPorts": {
            "FromPort": 9000,
            "ToPort": 9001
        },
        "ClusterPorts": {
            "FromPort": 7997,
            "ToPort": 8002
        },
        "ConfigVolumes": [{
            "Encrypted": "false",
            "VolumeType": "gp2",
            "Iops": "10",
            "Size": "10",
            "FromSnapshot": "true",
            "SnapshotId": "snap-41163b47",
            "DeletionPolicy": "Delete",
            "Device": "/dev/sdb",
            "MountDirectory": "/var/opt/MarkLogic"
        }],
        "DataVolumes": [{
            "Encrypted": "false",
            "VolumeType": "gp2",
            "Iops": "10",
            "Size": "10",
            "FromSnapshot": "true",
            "SnapshotId": "snap-41163b47",
            "DeletionPolicy": "Delete",
            "Device": "/dev/sdc",
            "MountDirectory": "/var/opt/data"
        }],
        "Alarms": [
        ]
    }

    def test_get_subnet_id(self):
        self.assertEqual("subnet-c4e4deef", ml_stack.get_private_subnet_id(self.aws_config, "b"))
        self.assertEqual("subnet-1558a563", ml_stack.get_private_subnet_id(self.aws_config, "c"))
        self.assertEqual("subnet-e04ef1dd", ml_stack.get_private_subnet_id(self.aws_config, "e"))

    def test_create_network_interface(self):
        network_interface = ml_stack.create_network_interface(self.aws_config, self.config, "b", 1, [], "test")
        self.assertEqual("testMarkLogicCluster01ENIb1", network_interface.title)

if __name__ == '__main__':
    unittest.main()
