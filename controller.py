'''
Please add your name: John Alec Mendoza Branzuela
Please add your matric number: A0201504B
'''

import sys
import os

from pox.core import core

import pox.openflow.libopenflow_01 as of
import pox.openflow.discovery
import pox.openflow.spanning_forest

from pox.lib.revent import *
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr

import time
import datetime

log = core.getLogger()

TTL = 10
hard_TTL = TTL
idle_TTL = TTL

PREMIUM = 1
NORMAL = 0

PREMIUM_PRIORITY = 100
FIREWALL_PRIORITY = 200

class Controller(EventMixin):
    def __init__(self):
        self.listenTo(core.openflow)
        core.openflow_discovery.addListeners(self)
        #Tables to store mac addresses and ports 
        self.mac_tables = {}
        self.ttl_tables = {}
        #self.policies = [] #src, dst, port
        self.premium = []
        

    def _handle_PacketIn (self, event):
        packet = event.parsed
        #Get source and dest IP address from the packet
        dest = packet.dst
        source = packet.src
        ip_dest = None
        ip_source = None
        dpid = event.dpid
        inport = event.port
            
    	# Install entries to the route table
        def enqueue_entries(packet, event, queue_id, outport):    
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, inport)
            msg.priority = PREMIUM_PRIORITY
            msg.actions.append(of.ofp_action_enqueue(port = outport, queue_id = queue_id))
            msg.data = event.ofp
            msg.hard_timeout = hard_TTL
            msg.idle_timeout = idle_TTL
            event.connection.send(msg)
            return

        def clear_expired():
             assert(dpid in self.ttl_tables)
             if dest in self.ttl_tables[dpid] and self.ttl_tables[dpid][dest] + datetime.timedelta(seconds=TTL) <= datetime.datetime.now():
                self.mac_tables[dpid].pop(dest)
                self.ttl_tables[dpid].pop(dest)

    	# Check the packet and decide how to route the packet
        def forward(message = None):
            
            # if port to reach dest is not found, packet is flooded (task 2)
            #create table for unknown dst
            if dpid not in self.mac_tables:
                self.mac_tables[dpid] = {}
                self.ttl_tables[dpid] = {}
            
            if self.mac_tables[dpid].get(source) == None:
                self.mac_tables[dpid][source] = inport
                self.ttl_tables[dpid][source] = datetime.datetime.now()
            
            #Check the packet type and obtain the IP address
            if packet.type == packet.IP_TYPE: #if packet type is IP
                ip_dest = packet.payload.dstip   
                ip_source = packet.payload.srcip         
            elif packet.type == packet.ARP_TYPE: #if packet type is ARP
                ip_dest = packet.payload.protodst
                ip_source = packet.payload.protosrc
            

            queue_id = NORMAL
            #For when both source and dest ip are premium
            if(ip_dest in self.premium and ip_source in self.premium):
                queue_id = PREMIUM 

            # if packet dest is a multicast, packet is flooded
            if dest.is_multicast:
                return flood("Multicast to dest %s -- flooding" % (dest))
            
            if dest not in self.mac_tables[dpid]:
                return flood("Destination dest %s unknown -- flooding" % (dest))
 
                #Add the node in_port to route table for learning switch (task 2)
            outport = self.mac_tables[dpid][dest] #get outport for known dst
            enqueue_entries(packet, event, queue_id, outport)

            
        # When it knows nothing about the destination, flood but don't install the rule (Task 2)
        def flood (message = None):
            # define your message here
            log.debug(message)
            msg = of.ofp_packet_out()
            msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
            msg.data = event.ofp
            msg.in_port = inport
            event.connection.send(msg)
            log.info("Flooding...")
            return

        forward()
        clear_expired()
        return


    def _handle_ConnectionUp(self, event):
        dpid = dpid_to_str(event.dpid)
        log.debug("Switch %s has come up.", dpid)
        
        def readPolicy():
            policies = []
            #premium = []
            
            #read policies
            f = open("policy.in", "r")
            firstline = f.readline().split(" ")
            num_fw = firstline[0]
            num_pre = firstline[1]
            
            #store firewall policies
            for rule in range(int(num_fw)):
                l = f.readline().strip().split(",")
                if len(l) == 2:
                    policies.append((None, l[0], l[1]))
                elif len(l) == 3:
                    policies.append((l[0], l[1], l[2]))

            #store premium policies
            for host in range(int(num_pre)):
                a = f.readline()
                self.premium.append(a)

            return policies


        # Send the firewall policies to the switch
        def sendFirewallPolicy(connection, policy):
            # define your message here
            from_host, to_host, outport = policy
            print(from_host, to_host, outport)
            msg = of.ofp_flow_mod()
            msg.priority = FIREWALL_PRIORITY
            #msg.actions.append(of.ofp_action_output(port = of.OFPP_NONE))
            #if block by firewall, drop message
            msg.match.dl_type = 0x800
            # only block tcp, so header protocol should be 6
            msg.match.nw_proto = 6
            
            #only block to host
            if from_host is not None:
                msg.match.nw_src = IPAddr(from_host)
 
            msg.match.nw_dst = IPAddr(to_host)
            msg.match.tp_dst = int(outport)
                
            connection.send(msg)

        policies = readPolicy()
        for policy in policies:
            sendFirewallPolicy(event.connection, policy)
            

def launch():
    # Run discovery and spanning tree modules
    pox.openflow.discovery.launch()
    pox.openflow.spanning_forest.launch()

    # Starting the controller module
    core.registerNew(Controller)
