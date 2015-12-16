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
import docopt
import logging
import requests
from xml.etree import ElementTree
from getpass import getpass
from requests.auth import HTTPDigestAuth

RETRY_COUNT = 15
RETRY_WAIT_MULTIPLIER = 1

def print_response(url, response):
    print("Url : %s status_code : %s response : %s" % (url, response.status_code, response.text))

def post(url, data, headers, timeout=60, auth=None):
    print ("Post url : " + url)
    r = requests.post(url, headers=headers, data=data, timeout=timeout, allow_redirects=True, auth=auth)
    print(url, r)
    return r

def get(url, timeout=60, auth=None):
    print("Get url : "+url)
    response = requests.get(url, timeout=timeout, allow_redirects=True, auth=auth)
    print(url, response)
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
                response = get("http://%s:8001/admin/v1/timestamp" % host, auth)
                if response.status_code == 200:
                    new_time_stamp = response.text.strip()
                    print("New timestamp : %s" % new_time_stamp)
                else:
                    print("Response : %s" % response.text)
            except Exception:
                pass


def initialize_cluster(hosts, config):
    master_host = hosts[0]
    headers = {'Content-Type': 'application/xml'}
    print("Initializing Bootstrap Host %s" % master_host)
    init_data = '<init xmlns="http://marklogic.com/manage"><license-key>'+config["license-key"]+'</license-key><licensee>'+config["licensee"]+'</licensee></init>'
    post_and_await_restart(master_host, "http://%s:8001/admin/v1/init" % master_host, init_data, headers)

    admin_password=getpass("Please enter admin password for Marklogic :")
    print("Setting admin password")
    admin_password_data='<instance-admin xmlns="http://marklogic.com/manage"><admin-password>'+admin_password+'</admin-password><admin-username>admin</admin-username><realm>public</realm></instance-admin>'
    auth = HTTPDigestAuth("admin", admin_password)
    post_and_await_restart(master_host, "http://%s:8001/admin/v1/instance-admin" % master_host, admin_password_data, headers,
                           auth)

    print("Setting hostname for %s" % master_host)
    hostname_data = '<host-properties xmlns="http://marklogic.com/manage"><host-name>'+master_host+'</host-name></host-properties>'
    post_and_await_restart(master_host, "http://%s:8002/manage/v2/hosts/%s/properties" % (master_host, master_host), hostname_data, headers, auth)

    print("Host %s configured" % master_host)
"""
echo "Setting hostname for ${master_host} : ${hostname}"
curl_and_await_restart '-s' '-S' '--digest' '--user' "admin:${password}" '-X' 'PUT' '-H' "'Content-type: application/xml'" '-d' "\"<host-properties xmlns='http://marklogic.com/manage'><host-name>${master_host}</host-name></host-properties>\"" "'http://${master_host}:8002/manage/v2/hosts/${hostname}/properties'"

echo "${master_host} configured"

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

    initialize_cluster(())

