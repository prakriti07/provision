#! /usr/bin/env python
# Copyright 2017, RackN
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pip install requests
import requests, argparse, json, urllib3, os

'''
Usage: https://github.com/digitalrebar/provision/v4/tree/master/integration/ansible

example: ansible -i inventory.py all -a "uname -a"
'''

def main():

    inventory = { "_meta": { "hostvars": {} } }

    # change these values to match your DigitalRebar installation
    addr = os.getenv('RS_ENDPOINT', "https://127.0.0.1:8092")
    ups = os.getenv('RS_KEY', "rocketskates:r0cketsk8ts")
    profile = os.getenv('RS_PROFILE', "mycluster")
    arr = ups.split(":")
    user = arr[0]
    password = arr[1]

    # Argument parsing 
    parser = argparse.ArgumentParser(description="Ansible dynamic inventory via DigitalRebar")
    parser.add_argument("--list", help="Ansible inventory of all of the deployments", 
        action="store_true", dest="list_inventory")
    parser.add_argument("--host",
        help="Ansible inventory of a particular host", action="store",
        dest="ansible_host", type=str)

    cli_args = parser.parse_args()
    list_inventory = cli_args.list_inventory
    ansible_host = cli_args.ansible_host

    Headers = {'content-type': 'application/json'}
    urllib3.disable_warnings()
    inventory["_meta"]["rebar_url"] = addr
    inventory["_meta"]["rebar_user"] = user
    inventory["_meta"]["rebar_profile"] = profile

    groups = []
    profiles = {}
    profiles_vars = {}

    profile_raw = requests.get(addr + "/api/v3/profiles/" + profile + "/params",headers=Headers,auth=(user,password),verify=False)
    if profile_raw.status_code == 200: 
        params = profile_raw.json()
        if u"ansible/groups" in params:
            groups = params[u"ansible/groups"]
        else:
            raise IOError("cannot parse profile " + profile + ": missing ansible/groups param.")
        if u"ansible/groups-members" in params:
            members = params[u"ansible/groups-members"]
        else:
            raise IOError("cannot parse profile " + profile + ": missing ansible/groups-members")
        if u"ansible/groupvars" in params:    
            groupvars = params[u"ansible/groupvars"]
        else:
            groupvars = {}
        if u"ansible/hostvars" in params:
            hostvars = params[u"ansible/hostvars"]
        else:
            hostvars = {}
        if u"ansible/parent-groups" in params:
            parentgroups = params[u"ansible/parent-groups"]
        else:
            parentgroups = []
    else:
        raise IOError(profile_raw.text)

    if list_inventory:
        URL = addr + "/api/v3/machines"
    elif ansible_host:
        URL = addr + "/api/v3/machines?Name=" + ansible_host
    else:
        URL = addr + "/api/v3/machines"

    raw = requests.get(URL,headers=Headers,auth=(user,password),verify=False)
    if raw.status_code == 200: 
        for machine in raw.json():
            name = machine[u'Name']
            myvars = hostvars.copy()
            if u"Params" in machine[u'Profile'] and machine[u'Profile'][u'Params']:
                for k in machine[u'Profile'][u'Params']:
                    myvars[k] = machine[u'Profile'][u'Params'][k]
            myvars["ansible_host"] = machine[u"Address"]
            myvars["rebar_uuid"] = machine[u"Uuid"]
            inventory["_meta"]["hostvars"][name] = myvars
    else:
        raise IOError(raw.text)

    # collect group information
    for group in groups:
        inventory[group] = {}
        inventory[group]['hosts'] = members[group]
        if group in groupvars:
            inventory[group]['vars'] = {}
            URL = addr + "/api/v3/profiles/" + groupvars[group] + "/params"
            raw = requests.get(URL,headers=Headers,auth=(user,password),verify=False)
            if raw.status_code == 200: 
                inventory[group]['vars'] = raw.json() 

    # add child groups
    for group in parentgroups:
        if not group in inventory:
            inventory[group] = { 'children': [] }
        else:
            inventory[group]['children'] = []
        inventory[group]['children'] = parentgroups[group] 

    print json.dumps(inventory)

if __name__ == "__main__":
    main()  
