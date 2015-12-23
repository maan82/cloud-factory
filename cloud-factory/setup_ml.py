# /usr/bin/env python

"""MarkLogic CloudFormation template generator.

Usage:
    setup_ml.py [-v] -f CONFIGURATION_FILE ENV

Options:
    -f <file> cluster configuration file
"""
import boto
import json
import urllib2
import commands
import os
import time
from boto.exception import EC2ResponseError
from docopt import docopt
import logging
import requests
from xml.etree import ElementTree
from getpass import getpass
from requests.auth import HTTPDigestAuth
import collections
import ml_stack

RETRY_COUNT = 15
RETRY_WAIT_MULTIPLIER = 1

def print_response(url, response):
    print("Url : %s status_code : %s response : %s" % (url, response.status_code, response.text))

def post(url, data, headers, auth=None):
    if isinstance(data, dict):
        print(("Post url : %s data : %s headers : %s" % (url, data, headers)))
    else:
        print(("Post url : %s data : %s headers : %s" % (url, "Non dictionery data", headers)))

    if auth is not None:
	    print("auth : "+str(auth))
    else:
        print("auth is None")
    r = requests.post(url, headers=headers, data=data, allow_redirects=True, auth=auth)
    print_response(url, r)
    return r

def put(url, data, headers, auth=None):
    print(("Post url : %s data : %s headers : %s" % (url, data, headers)))
    if auth is not None:
        print("auth : "+str(auth))
    else:
        print("auth is None")
    r = requests.put(url, headers=headers, data=data, allow_redirects=True, auth=auth)
    print_response(url, r)
    return r

def get(url, auth=None, headers=None):
    print("Get url : "+url)
    if auth is not None:
        print("auth : "+str(auth))
    else:
        print("auth is None")
    response = requests.get(url, allow_redirects=True, auth=auth, headers=headers)
    print_response(url, response)
    return response

def post_and_await_restart(host, url, data, headers, auth=None):
    response = post(url, data, headers, auth)
    return process_response(auth, host, response)


def process_response(auth, host, response):
    if response.status_code == 202:
        return await_restart(auth, host, response)
    elif response.status_code == 204:
        print("Timestamp check not required. Response status_code : %s" % response.status_code)
        return response
    else:
        raise Exception("Unexpected response status_code : %s" % response.status_code)


def put_and_await_restart(host, url, data, headers, auth=None):
    response = put(url, data, headers, auth)
    return process_response(auth, host, response)

def await_restart(auth, host, response):
    element_tree = ElementTree.fromstring(response.text)
    ml_namespace = "http://marklogic.com/manage"
    time_stamp = element_tree.findall("./{%s}last-startup" % ml_namespace)[0].text.strip()
    new_time_stamp = ""
    count = 0
    while count < RETRY_COUNT and new_time_stamp == "" or new_time_stamp == time_stamp:
        try:
            count = count + 1
            time.sleep(count)
            response = get(("http://%s:8001/admin/v1/timestamp" % host), auth)
            if response.status_code == 200:
                new_time_stamp = response.text.strip()
        except Exception:
            pass
    if new_time_stamp == "" or new_time_stamp == time_stamp:
        raise Exception("Timestamp has not changed after retries : %s " % RETRY_COUNT)
    return response

def find_instances_in_cluster(env, config):
    conn = boto.connect_ec2()
    stack_name = ml_stack.get_name_prefix(env, config)
    instances = conn.get_all_instances(filters={"tag:aws:cloudformation:stack-name": stack_name})
    return instances

def get_private_dns(instance):
    return instance.private_dns_name

def get_permanent_ip(instance):
    return instance.interfaces[1].private_ip_address

def set_host_name(auth, headers, instance, permanent_host_ip):
    print("Setting hostname for %s" % permanent_host_ip)
    hostname_data = '<host-properties xmlns="http://marklogic.com/manage"><host-name>' + permanent_host_ip + '</host-name></host-properties>'
    private_dns = get_private_dns(instance)
    print("Found private_dns : %s for master_host : %s" % (private_dns, permanent_host_ip))
    put_and_await_restart(permanent_host_ip, ("http://%s:8002/manage/v2/hosts/%s/properties" % (permanent_host_ip, private_dns)), hostname_data, headers, auth)
    print("Host %s configured" % permanent_host_ip)

def initialize_cluster(instances, config):
    master_host = get_permanent_ip(instances[0])
    headers = get_xml_content_type_header()
    print("Initializing Bootstrap Host %s" % master_host)
    init_data = '<init xmlns="http://marklogic.com/manage"><license-key>'+config["license-key"]+'</license-key><licensee>'+config["licensee"]+'</licensee></init>'
    post_and_await_restart(master_host, ("http://%s:8001/admin/v1/init" % master_host), init_data, headers)

    admin_password=getpass("Please enter admin password for Marklogic :")
    print("Setting admin password")
    admin_password_data='<instance-admin xmlns="http://marklogic.com/manage"><admin-password>'+admin_password+'</admin-password><admin-username>admin</admin-username><realm>public</realm></instance-admin>'
    auth = HTTPDigestAuth("admin", admin_password)
    post_and_await_restart(master_host, "http://%s:8001/admin/v1/instance-admin" % master_host, admin_password_data, headers,
                           auth=auth)

    set_host_name(auth, headers, instances[0], master_host)

    remaining_instances = [instances[index] for index in range(1, len(instances))]

    for instance in remaining_instances:
        permanent_ip = get_permanent_ip(instance)
        print("Initializing host : %s" % permanent_ip)
        post_and_await_restart(permanent_ip, "http://%s:8001/admin/v1/init" % permanent_ip, init_data, headers)
        print("Getting server-config from host : %s" % permanent_ip)
        response = get(("http://%s:8001/admin/v1/server-config" % permanent_ip), auth=None, headers={"Accept": "application/xml"})
        if response.status_code == 200:
            joiner_config = response.text
            print(("Getting cluster-config from master : %s" % master_host))
            master_response = post(("http://%s:8001/admin/v1/cluster-config" % master_host), {"server-config": joiner_config, "group":"Default"},
                         headers={'Content-Type': 'application/x-www-form-urlencoded'}, auth=auth)
            if master_response.status_code == 200:
                cluster_config_from_master = master_response.content
                print("Joining host : %s to cluster" % permanent_ip)
                response = post_and_await_restart(permanent_ip, ("http://%s:8001/admin/v1/cluster-config" % permanent_ip), data=cluster_config_from_master,
                             headers={"Content-type": "application/zip"}, auth=auth)
                set_host_name(auth, get_xml_content_type_header(), instance, permanent_ip)

        else:
            message = "Failed to get joiner config"
            print(message)
            raise Exception(message)
    return auth


def find_instances(env, config):
    instances = []
    reservations = find_instances_in_cluster(env, config)
    for reservation in reservations:
        for instance in reservation.instances:
            instances.append(instance)
    return instances

def create_databases(instances, config, auth):
    for database_configuration in config["DataBaseConfigurations"]:
        for database_name in database_configuration:
            create_database(config, auth, database_name, get_permanent_ip(instances[0]))

    forest_index = 1
    for volume_number, volume in enumerate(config["DataVolumes"], start=1):
        for database in volume["Databases"]:
            for instance_index, instance in enumerate(instances):
                for forest_number, forest in enumerate(range(int(database["NumberOfforestsPerDisk"])), start=1):
                    instances_count = len(instances)
                    if instances_count > 1:
                        instances_per_zone = config["NumberOfInstancesPerZone"]
                        instances_index = range(instances_count)
                        rotated_index = instances_index[instances_per_zone + (forest_number - 1):] + instances_index[:instances_per_zone + (forest_number - 1)]
                        instance_ip = get_permanent_ip(instance)
                        forest_name = database["database-name"]+"-forest-"+format_number(forest_index)+"-node-"+format_number(instance_index+1)
                        replica_instance_index = rotated_index[instance_index]
                        replica_forest_name = "R-"+database["database-name"]+ "-forest-" + format_number(forest_index) +"-node-" + format_number(replica_instance_index+1)
                        forest_create_body = {
                            "forest-name": forest_name,
                            "host": instance_ip,
                            "database": database["database-name"],
                            "data-directory": volume["MountDirectory"],
                            "large-data-directory": volume["MountDirectory"],
                            "fast-data-directory": volume["MountDirectory"],
                            "forest-replicas": {
                                "forest-replica": [
                                    {
                                        "replica-name": replica_forest_name,
                                        "host": get_permanent_ip(instances[replica_instance_index]),
                                        "data-directory": volume["MountDirectory"],
                                        "large-data-directory": volume["MountDirectory"],
                                        "fast-data-directory": volume["MountDirectory"],
                                    }
                                ]
                            }
                        }
                        response = post(("http://%s:8002/manage/v2/forests" % instance_ip), json.dumps(forest_create_body),
                                        get_json_content_type_header(), auth)
                        forest_index += 1
                        if response.status_code != 201:
                            raise Exception("Failed to create forests.")


def add_forests(master_instance, other_instances, database_name):
    for instance_index, instance in enumerate(other_instances):
        instance_ip = get_permanent_ip(instance)
        forest_name = database_name + "-forest-" + format_number(instance_index + 1) + "-node-" + format_number(
            instance_index + 1)
        forest_create_body = {
            "forest-name": forest_name,
            "host": instance_ip,
            "database": database_name,
        }
        response = post(("http://%s:8002/manage/v2/forests" % instance_ip), json.dumps(forest_create_body),
                        get_json_content_type_header(), auth)
        if response.status_code != 201:
            raise Exception("Failed to create forests.")

def format_number(number):
    return "%03d" % number

def get_json_content_type_header():
    return {"Content-Type": "application/json"}

def get_xml_content_type_header():
    return {"Content-Type": "application/xml"}

def create_database(config, auth, database_name, host_ip):
    database_create_body = {"database-name": database_name}
    for database_configuration in config["DataBaseConfigurations"]:
        if database_name in database_configuration:
            database_create_body.update(database_configuration[database_name])

    response = post(("http://%s:8002/manage/v2/databases" % host_ip), json.dumps(database_create_body),
                    get_json_content_type_header(), auth)
    if response.status_code != 201:
        raise Exception("Failed database creation")


def create_forest_replicas(master_instance, replica_instances, database_name):
    replica_list = []
    for index, instance in enumerate(replica_instances, start=1):
        replica_forest_name = "R-"+database_name+ "-forest-" + format_number(index)
        permanent_ip = get_permanent_ip(instance)
        replica_list.append({
            "replica-name": replica_forest_name,
            "host": permanent_ip
        })

    create_forest_body = {
        "forest-name": database_name,
        "database": database_name,
        "forest-replica": [replica_list]
    }

    response = put(("http://%s:8002/manage/v2/forests/%s/properties" % (get_permanent_ip(master_instance), database_name)), json.dumps(create_forest_body),
                    get_json_content_type_header(), auth)

    if response.status_code != 204:
        raise Exception("Failed to create replica forest : %s on host : %s" % (replica_forest_name, permanent_ip))




if __name__ == "__main__":
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

    instances = find_instances(env, config)
    sorted_instances = sorted(instances, key=lambda instance: get_permanent_ip(instance))
    sorted_instances = sorted(sorted_instances, key=lambda instance: instance.placement)

    print("Found instances count : %d " % len(instances))
    auth = initialize_cluster(sorted_instances, config)

    create_databases(sorted_instances, config, auth)

    for database_name in config["DataBasesToConfigureForestReplication"]:
        create_forest_replicas(sorted_instances[0], sorted_instances[1:], database_name)

    for database_name in config["DataBasesToAddForestsOnConfigVolume"]:
        add_forests(sorted_instances[0], sorted_instances[1:], database_name)
