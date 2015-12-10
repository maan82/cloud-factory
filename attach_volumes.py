import boto
import json
import urllib2
import commands
import os
import time

RETRY_COUNT=5
RETRY_WAIT_MULTIPLIER=1

def print_command_output_status(command, status, output):
    print "INFO executed command : %s status : %s output : %s" % (command, status, output)

def run_command(command):
    status, output = commands.getstatusoutput(command)
    print_command_output_status(command, status, output)

def attach_volume(volume, instance_id, device):
    if volume.status == "available":
        volume_attach_result = conn.attach_volume(volume.id, instance_id, device)
        print "Volume attach result : "+str(volume_attach_result)
        count = 0
        while(count < RETRY_COUNT and not os.path.exists(device)):
            seconds = count * RETRY_WAIT_MULTIPLIER + 1
            print "INFO waiting for device : %s to appear" % (device)
            print "INFO sleeping for %s seconds" % (seconds)
            time.sleep(seconds)
            count += 1

def attach_network_interface(network_interface, instance_id, device_index):
    if network_interface.status == "available":
        network_interface_attach_result = conn.attach_network_interface(network_interface.id, instance_id, device_index)
        print "Network Interface attach result : "+str(network_interface_attach_result)

def mount_volume(device, mount_point):
    if not os.path.isdir(mount_point):
        run_command("sudo mkdir -p " + mount_point)
        run_command("sudo chown daemon:daemon " + mount_point)
    run_command("sudo mount "+device+" "+mount_point)

def start_marklogic():
    run_command("sudo service MarkLogic start")

def stop_marklogic():
    run_command("sudo service MarkLogic stop")


if __name__ == "__main__":
    conn = boto.connect_ec2()
    with open("/etc/instance.conf") as aws_config_file:
        instance_config = json.load(aws_config_file)

    stop_marklogic()

    config_volume = conn.get_all_volumes(None, filters={"tag:aws:cloudformation:stack-name": "rasingh-MarkLogic-ml-master", "tag:zone": instance_config["zone"], "tag:instance": str(instance_config["instanceNumber"]), "tag:type": "ConfigVolume"})[0]
    print "Found config volume : "+str(config_volume)

    data_volume = conn.get_all_volumes(None, filters={"tag:aws:cloudformation:stack-name": "rasingh-MarkLogic-ml-master", "tag:zone": instance_config["zone"], "tag:instance": str(instance_config["instanceNumber"]), "tag:type": "DataVolume"})[0]
    print "Found data volume : "+str(data_volume)

    network_interface = conn.get_all_network_interfaces(None, filters={"tag:aws:cloudformation:stack-name": "rasingh-MarkLogic-ml-master", "tag:zone": instance_config["zone"], "tag:instance": str(instance_config["instanceNumber"])})[0]
    print "Found network interface : "+str(network_interface)

    instance_id = urllib2.urlopen("http://169.254.169.254/latest/meta-data/instance-id").read()
    print "Found instance id : "+str(instance_id)

    attach_volume(config_volume, instance_id, "/dev/sdb")
    attach_volume(data_volume, instance_id, "/dev/sdc")
    attach_network_interface(network_interface, instance_id, 1)
    mount_volume("/dev/sdb", "/var/opt/MarkLogic")
    mount_volume("/dev/sdc", "/var/opt/data")
    start_marklogic()


