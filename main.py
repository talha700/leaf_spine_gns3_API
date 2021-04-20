import requests
import sys
import json
import jinja2
import time
from netmiko import ConnectHandler
from .constants import (
                ipterms,
                devices,
                compute_id,
                node_type,
                symbol,
                properties
            )



GNS3VM = input("GNS3VM IP: ")
project_name = {"name":"leaf_spine_topology"}
url = f"http://{GNS3VM}/v2/"


# Check GNS3VM connectivity
try:
    response = requests.get(url + "version")
    if response.status_code == 200:
        print("Connectivity....OK!")
except:
    print("Can not reach GNS3")
    exit()



# Creating a new project 
response = requests.post(url + "projects" , data=json.dumps(project_name))
project_id = json.loads(response.text)['project_id']


# Creating a structured data for leafs and spines 
data=[]
for name in devices:
    device = {
        "node_type":node_type,
        "compute_id":compute_id,
        "name":name,
        "symbol":symbol,
        "properties": properties
    }
    data.append(device)


# Creating Nodes
print("Creating Nodes...")
for device in data:
    create_nodes = requests.post(url + "projects/"+ project_id + "/nodes" ,data=json.dumps(device))


# create ipterms
ipterm_nodes = []
for ipterm in ipterms:
    device = {
        "node_type":"docker",
        "console_type": "telnet",
        "compute_id":compute_id,
        "name":ipterm,
        "properties": {
            "image": "gns3/ipterm:latest"
        }
    }
    create_ipterms = requests.post(url + "projects/"+ project_id + "/nodes" , data=json.dumps(device))
    node_id = json.loads(create_ipterms.text)
    ipterm_nodes.append({"node_id":node_id['node_id'] ,"console_port":node_id['console'] , "node_name":node_id['name']})





#Get node IDs
print("Created.")
get_nodes = requests.get(url + "projects/"+ project_id + "/nodes")
all_nodes = json.loads(get_nodes.text)



# create links for ipterms
leaf_num = 0
for ipterm_node in ipterm_nodes:
    leaf_num += 1
    links = {}
    links['nodes'] = []
    for node in all_nodes:
        if node['name'] == 'leaf'+str(leaf_num):
            ipterm_port = {"adapter_number": 0,"node_id":ipterm_node['node_id'],
                                    "port_number":0}
            leaf_port = {"adapter_number": 1,"node_id":node['node_id'],
                                    "port_number":0}
            
            links['nodes'].append(ipterm_port)
            links['nodes'].append(leaf_port)

            result = requests.post(url + "projects/" + project_id + "/links" , data=json.dumps(links))





nodes = []
for node in all_nodes:
    node_id = node['node_id']
    node_name = node['name']

    nodes.append({"name":node_name , "node_id":node_id })



# split leafs and spines 
spines = []
leafes = []

for node in nodes:
    if "spine" in node["name"]:
        spines.append(node)
    else:
        leafes.append(node)



# Creating Links
print("Creating Links....")
leaf_adapter_number = 0
leaf_port_number = 0

for spine in spines:

    spine_port_number = 0
    spine_adapter_number = 0

    for leaf in leafes:

        if spine_port_number >= 4:
            spine_adapter_number = 1
            spine_port_number = 0 

        links ={}
        links['nodes']=[]

        spine_port = {"adapter_number": spine_adapter_number,"node_id":spine['node_id'],
                            "port_number":spine_port_number}
        
        links['nodes'].append({"adapter_number": leaf_adapter_number,"node_id":leaf['node_id'],
            "port_number":leaf_port_number})

        links['nodes'].append(spine_port)

        result = requests.post(url + "projects/" + project_id + "/links" , data=json.dumps(links))

        # spine_adapter_number += 1
        spine_port_number += 1
        
    
    # leaf_adapter_number += 1
    leaf_port_number += 1
print("Created.")



network = "192.168.1."

with open("startup-config.jinja2") as file:
    template = file.read()


# create a startup-config for each node 
host_ip = 0
for node in nodes:
    host_ip +=1
    templateLoader = jinja2.FileSystemLoader(searchpath="./")
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = "startup-config.jinja2"
    template = templateEnv.get_template(TEMPLATE_FILE)
    outputText = template.render(ip=network+str(host_ip)) 
    response = requests.post(url + "projects/" + project_id + "/nodes/" + node["node_id"] + "/files/startup-config.cfg" ,data=outputText)



# start all nodes
requests.post(url + "projects/" + project_id + "/nodes/" +"start")
time.sleep(5)



# give static IPs to Ipterms
ipterm_ip_range = "192.168.1."
ip = 20
index = 0
for ipterm in ipterm_nodes:
    index += 1
    ip += 1
    ipterm_ip = ipterm_ip_range + str(ip)
    command = f"ifconfig eth0 {ipterm_ip}/24"
    conn = ConnectHandler(ip=GNS3VM , port=ipterm['console_port'] , device_type='generic_telnet')
    conn.send_command(command)
    conn.disconnect()

