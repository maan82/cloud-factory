# /usr/bin/env python

"""MarkLogic CloudFormation template generator.

Usage:
    setup_ml.py [-v] -f CONFIGURATION_FILE ENV

Options:
    -f <file> cluster configuration file
"""
import json
import urllib2
import commands
import os
import time
import logging
import requests
from xml.etree import ElementTree
from getpass import getpass

from requests.auth import HTTPDigestAuth

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

def get(url, auth=None):
    print("Get url : "+url)
    if auth is not None:
        print("auth : "+str(auth))
    else:
        print("auth is None")
    response = requests.get(url, allow_redirects=True, auth=auth)
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


def initialize_cluster(hosts, config):
    master_host = hosts[0]
    headers = headers = {'Content-Type': 'application/xml'}
    print("Initializing Bootstrap Host %s" % master_host)
    init_data = '<init xmlns="http://marklogic.com/manage"><license-key>'+config["license-key"]+'</license-key><licensee>'+config["licensee"]+'</licensee></init>'
    post_and_await_restart(master_host, "http://%s:8001/admin/v1/init" % master_host, init_data, headers)

    admin_password=getpass("Please enter admin password for Marklogic :")
    print("Setting admin password")
    admin_password_data='<instance-admin xmlns="http://marklogic.com/manage"><admin-password>'+admin_password+'</admin-password><admin-username>admin</admin-username><realm>public</realm></instance-admin>'
    auth = HTTPDigestAuth("admin", admin_password)
    print("Admin password:'%s'" % admin_password)
    print("****************")
    post_and_await_restart(master_host, "http://%s:8001/admin/v1/instance-admin" % master_host, admin_password_data, headers,
                           auth)

    print("Setting hostname for %s" % master_host)
    hostname_data = '<host-properties xmlns="http://marklogic.com/manage"><host-name>'+master_host+'</host-name></host-properties>'
    put("http://%s:8002/manage/v2/hosts/%s/properties" % (master_host, master_host), hostname_data, headers, auth)

    print("Host %s configured" % master_host)



if __name__ == "__main__":



    with open('conf/aws_config.json') as aws_config_file:
        aws_config = json.load(aws_config_file)

    with open('conf/marklogic_cluster01.json') as config_file:
        config = json.load(config_file)

    initialize_cluster(["52.21.43.120"], config)
