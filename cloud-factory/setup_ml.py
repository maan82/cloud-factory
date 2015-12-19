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
import ml_stack

RETRY_COUNT = 15
RETRY_WAIT_MULTIPLIER = 1

def print_response(url, response):
    print("Url : %s status_code : %s response : %s" % (url, response.status_code, response.text))

def post(url, data, headers, auth=None):
    print("Post url : " + url)
    if auth is not None:
	print("auth : "+str(auth))
    else:
        print("auth is None")
    r = requests.post(url, headers=headers, data=data, allow_redirects=True, auth=auth)
    print_response(url, r)
    return r

def put(url, data, headers, auth=None):
    print("Post url : " + url)
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
    if response.status_code == 202:
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
    put("http://%s:8002/manage/v2/hosts/%s/properties" % (permanent_host_ip, private_dns), hostname_data, headers, auth)
    print("Host %s configured" % permanent_host_ip)

def initialize_cluster(instances, config):
    master_host = get_permanent_ip(instances[0])
    headers = {'Content-Type': 'application/xml'}
    print("Initializing Bootstrap Host %s" % master_host)
    init_data = '<init xmlns="http://marklogic.com/manage"><license-key>'+config["license-key"]+'</license-key><licensee>'+config["licensee"]+'</licensee></init>'
    post_and_await_restart(master_host, ("http://%s:8001/admin/v1/init" % master_host), init_data, headers)

    admin_password=getpass("Please enter admin password for Marklogic :")
    print("Setting admin password")
    admin_password_data='<instance-admin xmlns="http://marklogic.com/manage"><admin-password>'+admin_password+'</admin-password><admin-username>admin</admin-username><realm>public</realm></instance-admin>'
    auth = HTTPDigestAuth("admin", admin_password)
    post_and_await_restart(master_host, "http://%s:8001/admin/v1/instance-admin" % master_host, admin_password_data, headers,
                           auth)

    set_host_name(auth, headers, instances[0], master_host)

    remaining_instances = [instances[index] for index in range(1, len(instances))]

    for instance in remaining_instances:
        permanent_ip = get_permanent_ip(instance)
        print("Initializing host : %s" % permanent_ip)
        post_and_await_restart(master_host, "http://%s:8001/admin/v1/init" % permanent_ip, init_data, headers)
        print("Getting server-config from host : %s" % permanent_ip)
        response = get("http://${host}:8001/admin/v1/server-config" % permanent_ip, auth, headers={"Accept": "application/xml"})
        if response.status_code == 200:
            joiner_config = response.text
            print(("Getting cluster-config from master : %s" % master_host))
            master_response = post(("http://%s:8001/admin/v1/cluster-config" % master_host), {"server-config": joiner_config},
                         headers={'Content-Type': 'application/x-www-form-urlencoded'}, auth=auth)
            if master_response.status_code == 202:
                cluster_config_from_master = master_response.content
                print("Joining host : %s to cluster" % permanent_ip)
                response = post(("http://%s:8001/admin/v1/cluster-config" % permanent_ip), data=cluster_config_from_master,
                             headers={'Content-type: application/zip'}, auth=auth)
                if response.status_code == 202:
                    set_host_name(auth, {'Content-Type': 'application/xml'}, instance, permanent_ip)
                else:
                    message = ("Failed to join cluster host : %s " %permanent_ip)
                    print(message)
                    raise Exception(message)

        else:
            message = "Failed to get joiner config"
            print(message)
            raise Exception(message)




"""
eval "oh=(${other_hosts[*]})"
for host in ${oh[@]} ; do

  echo "Initializing Other Host ${host}"

  curl_and_await_restart '-s' '-S' '-X' 'POST' '-d' "'license-key=${license_key}&licensee=${licensee}'" "'http://${host}:8001/admin/v1/init'"

  echo "Getting server-config from ${host}"
  joiner_config=`curl -s -S -X GET -H "Accept: application/xml" http://${host}:8001/admin/v1/server-config`

  echo "Getting cluster-config from ${master_host}"
  curl --digest --user "admin:${password}" -s -S -X POST -o /tmp/cluster-config.zip -d "group=Default" --data-urlencode "server-config=${joiner_config}" -H "Content-type: application/x-www-form-urlencoded" http://${master_host}:8001/admin/v1/cluster-config

  echo "Joining ${host} to cluster"
  curl_and_await_restart '-s' '-S' '-X' 'POST' '-H' "'Content-type: application/zip'" '--data-binary' '@/tmp/cluster-config.zip' "'http://${host}:8001/admin/v1/cluster-config'"

  host_underscores=${host//./_}
  hostname=$(eval echo \$host_${host_underscores})

  echo "Setting hostname for ${host} : ${hostname}"

  curl_and_await_restart '-s' '-S' '--digest' '--user' "'admin:${password}'" '-X' 'PUT' '-H' "'Content-type: application/xml'" '-d' "\"<host-properties xmlns='http://marklogic.com/manage'><host-name>${host}</host-name></host-properties>\"" "'http://${host}:8002/manage/v2/hosts/${hostname}/properties'"

done
"""


def find_instances(env, config):
    instances = []
    reservations = find_instances_in_cluster(env, config)
    for reservation in reservations:
        for instance in reservation.instances:
            instances.append(instance)
    return instances


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

    print("Found instances count : %d " % len(instances))
    initialize_cluster(instances, config)

