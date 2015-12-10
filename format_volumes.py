import commands
import boto
import json

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

if __name__ == '__main__':
    conn = boto.connect_ec2()
    with open('/etc/instance.conf') as aws_config_file:
        instance_config = json.load(aws_config_file)

    config_volume = conn.get_all_volumes(None, filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master', 'tag:zone': instance_config["zone"], 'tag:instance': str(instance_config["instanceNumber"]), 'tag:type': "ConfigVolume"})[0]
    print "Found config volume : "+str(config_volume)

    data_volume = conn.get_all_volumes(None, filters={'tag:aws:cloudformation:stack-name': 'rasingh-MarkLogic-ml-master', 'tag:zone': instance_config["zone"], 'tag:instance': str(instance_config["instanceNumber"]), 'tag:type': "DataVolume"})[0]
    print "Found data volume : "+str(data_volume)

    format_volume(config_volume.attach_data.device)
    format_volume(data_volume.attach_data.device)

