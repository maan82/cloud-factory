import boto
import json
import urllib2
import commands
import os
import time
from boto.exception import EC2ResponseError

RETRY_COUNT = 15
RETRY_WAIT_MULTIPLIER = 1


def log(message):
    print "%s %s" % (time.strftime("[%d/%b/%Y:%H:%M:%S %z]"), message)


def print_command_output_status(command, status, output):
    log("INFO executed command : %s status : %s output : %s" % (command, status, output))


def run_command(command):
    status, output = commands.getstatusoutput(command)
    print_command_output_status(command, status, output)
    return (status, output)


def attach_volume(volume, instance_id, device):
    count = 0
    alternate_device = get_alternative_name_for_device(device)
    while (count < RETRY_COUNT and not os.path.exists(device) and not os.path.exists(alternate_device)):
        log("INFO Volume status : %s" % (volume.status))
        if volume.status == "available":
            try:
                volume_attach_result = conn.attach_volume(volume.id, instance_id, device)
                time.sleep(2)
                log("INFO Volume attach result : " + str(volume_attach_result))
            except EC2ResponseError as e:
                log("INFO %s" % e)
        seconds = count * RETRY_WAIT_MULTIPLIER + 1
        log("INFO waiting for device : %s to appear" % (device))
        log("INFO sleeping for %s seconds" % (seconds))
        time.sleep(seconds)
        count += 1


def get_alternative_name_for_device(device):
    return "/dev/xvd" + device[-1:]


def attach_network_interface(network_interface, instance_id, device_index):
    count = 0
    while (count < RETRY_COUNT and int(run_command("ifconfig | grep 'eth' |wc -l")[1]) < 2):
        if network_interface.status == "available":
            try:
                network_interface_attach_result = conn.attach_network_interface(network_interface.id, instance_id,
                                                                                device_index)
                time.sleep(2)
                log("INFO Network Interface attach result : " + str(network_interface_attach_result))
            except EC2ResponseError as e:
                log("INFO %s" % e)
        seconds = count * RETRY_WAIT_MULTIPLIER + 1
        log("INFO waiting for network interface to appear")
        log("INFO sleeping for %s seconds" % (seconds))
        time.sleep(seconds)
        count += 1


def mount_volume(device, mount_point):
    if os.path.exists(device):
        device = device
    elif os.path.exists(get_alternative_name_for_device(device)):
        device = get_alternative_name_for_device(device)
    else:
        raise Exception("ERROR device : %s does not exist" % (device))

    if not os.path.isdir(mount_point):
        run_command("sudo mkdir -p " + mount_point)
        run_command("sudo chown daemon:daemon " + mount_point)
    run_command("sudo mount " + device + " " + mount_point)


def start_marklogic():
    run_command("sudo service MarkLogic start")


def stop_marklogic():
    run_command("sudo service MarkLogic stop")


def validate_volume_length(found_volumes, instance_config):
    if len(config_volumes) != len(instance_config):
        message = "ERROR config mismatch len(config_volumes) : %d len(instance_config['ConfigVolume']) : %d" % (
            len(config_volumes), len(instance_config))
        log(message)
        raise Exception(message)


if __name__ == "__main__":
    conn = boto.connect_ec2()
    with open("/etc/instance.conf") as aws_config_file:
        instance_config = json.load(aws_config_file)

    stop_marklogic()

    instance_id = urllib2.urlopen("http://169.254.169.254/latest/meta-data/instance-id").read()
    log("INFO Found instance id : " + str(instance_id))

    config_volumes = conn.get_all_volumes(None,
                                          filters={"tag:aws:cloudformation:stack-name": instance_config["stack-name"],
                                                   "tag:zone": instance_config["zone"],
                                                   "tag:instance": str(instance_config["instanceNumber"]),
                                                   "tag:type": "ConfigVolume"})

    log("INFO Found config volumes : %d " % (len(config_volumes)))
    validate_volume_length(config_volumes, instance_config["ConfigVolumes"])

    data_volumes = conn.get_all_volumes(None,
                                        filters={"tag:aws:cloudformation:stack-name": instance_config["stack-name"],
                                                 "tag:zone": instance_config["zone"],
                                                 "tag:instance": str(instance_config["instanceNumber"]),
                                                 "tag:type": "DataVolume"})
    log("INFO Found data volume : %d " % (len(data_volumes)))
    validate_volume_length(data_volumes, instance_config["DataVolumes"])

    network_interface = conn.get_all_network_interfaces(None, filters={
        "tag:aws:cloudformation:stack-name": instance_config["stack-name"], "tag:zone": instance_config["zone"],
        "tag:instance": str(instance_config["instanceNumber"])})[0]

    log("INFO Found network interface : " + str(network_interface))

    attach_network_interface(network_interface, instance_id, 1)

    for config_volume in config_volumes:
        attach_volume(config_volume, instance_id, config_volume.tags["Device"])
        mount_volume(config_volume.tags["Device"], config_volume.tags["MountDirectory"])

    for data_volume in data_volumes:
        attach_volume(data_volume, instance_id, data_volume.tags["Device"])
        mount_volume(data_volume.tags["Device"], data_volume.tags["MountDirectory"])

    start_marklogic()
