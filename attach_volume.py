import boto
import json
import urllib2
import commands
import os

def attach_volume(volume, instance_id, device):
    if volume.status == "available":
        volume_attach_result = conn.attach_volume(volume.id, instance_id, device)
        print "Volume attach result : "+str(volume_attach_result)

def attach_network_interface(network_interface, instance_id, device_index):
    if network_interface.status == "available":
        network_interface_attach_result = conn.attach_network_interface(network_interface.id, instance_id, device_index)
        print "Network Interface attach result : "+str(network_interface_attach_result)

def format_volume(device):
    file_system_status_command = "sudo file -s " + device
    status, output = commands.getstatusoutput(file_system_status_command)
    if status == 0:
        path = "/"+"/".join([device.split("/")[1],output.split()[-1]])
        status, output = commands.getstatusoutput("sudo file -s "+path)
        if status == 0 and output == path+": data":
            status, output = commands.getstatusoutput("sudo mkfs -t ext4 "+path)
            print output
            return path
        else:
            print "Volume %s is already formatted status : %s output : %s " % (device, status, output)
    else:
        print "Exiting: non zero status of command '%s' status : %s  output : %s" % (file_system_status_command, status, output)



def mount_volume(device, mount_point):
    if not os.path.isdir(mount_point):
        status, output = commands.getstatusoutput("sudo mkdir -p "+mount_point)
        print "Created directory : "+output
        status, output = commands.getstatusoutput("sudo chown daemon:daemon "+mount_point)
        print "Changed owner and group "+output
    status, output = commands.getstatusoutput("sudo mount "+device+" "+mount_point)
    print "Mountde "+device+" on "+mount_point+" output : "+output



if __name__ == '__main__':
    conn = boto.connect_ec2()
    with open('/etc/instance.conf') as aws_config_file:
        instance_config = json.load(aws_config_file)

    config_volume = conn.get_all_volumes(None, filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master', 'tag:zone': instance_config["zone"], 'tag:instance': str(instance_config["instanceNumber"]), 'tag:type': "ConfigVolume"})[0]
    print "Found config volume : "+str(config_volume)

    data_volume = conn.get_all_volumes(None, filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master', 'tag:zone': instance_config["zone"], 'tag:instance': str(instance_config["instanceNumber"]), 'tag:type': "DataVolume"})[0]
    print "Found data volume : "+str(data_volume)

    network_interface = conn.get_all_network_interfaces(None, filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master', 'tag:zone': instance_config["zone"], 'tag:instance': str(instance_config["instanceNumber"])})[0]
    print "Found network interface : "+str(network_interface)

    instance_id = urllib2.urlopen("http://169.254.169.254/latest/meta-data/instance-id").read()
    print "Found instance id : "+str(instance_id)

    attach_volume(config_volume, instance_id, "/dev/sdb")
    attach_volume(data_volume, instance_id, "/dev/sdc")
    attach_network_interface(network_interface, instance_id, 1)
