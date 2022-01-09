'''
Please add your name: John Alec Mendoza Branzuela
Please add your matric number: A0201504B
'''

import os
import sys
import atexit
 
from mininet.net import Mininet
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.link import Link
from mininet.link import TCLink
from mininet.node import RemoteController

net = None

class TreeTopo(Topo):
			
    def __init__(self):
		# Initialize topology
        Topo.__init__(self)  
        self.linkInfo = {}      

        file_name = "topology.in"
        f = open(file_name, "r")

        firstline = f.readline().split(" ")
        #get the number of host, switch and link
        num_host = int(firstline[0])
        num_switch = int(firstline[1])
        num_link = int(firstline[2])
     
        for host in range (num_host):
            self.addHost('h%s' % (host + 1)) #add host
        
        for switch in range (num_switch):
            sconfig = {'dpid': "%016x" % (switch + 1) }
            self.addSwitch('s%s' % (switch+ 1), **sconfig) #add switch

        for link in range (num_link):   
            link = f.readline().split(",")
            node1 = link[0]
            node2 = link[1]
            self.addLink(link[0], link[1]) #add link
            
            #add to bankwidth linkInfo, bi-direction 
            if link[0] not in self.linkInfo:
                self.linkInfo[link[0]] = {}
            
            if link[1] not in self.linkInfo:
                self.linkInfo[link[1]] = {}
            
            self.linkInfo[link[0]][link[1]] = int(link[2])
            self.linkInfo[link[1]][link[0]] = int(link[2])

def create(interface, bw):
    #Convert bw to Mbps
    bw = 1000000 * bw 
    premium = 0.8 * bw
    normal = 0.5 * bw 
    
    #create queue
    os.system('sudo ovs-vsctl -- set Port %s qos=@newqos \
                -- --id=@newqos create QoS type=linux-htb other-config:max-rate=%d queues=0=@q0,1=@q1\
                -- --id=@q0 create queue other-config:max-rate=%d \
                -- --id=@q1 create queue other-config:min-rate=%d'
                %(interface, bw, int(normal), int(premium)))


def startNetwork():
    info('** Creating the tree network\n')
    topo = TreeTopo()

    global net
    net = Mininet(topo=topo, link = Link,
                  controller=lambda name: RemoteController(name, ip='192.168.56.101'),
                  listenPort=6633, autoSetMacs=True)

    info('** Starting the network\n')
    net.start()
    

    # Create QoS Queues
    for switch in net.switches: #check all the switches
        for intf in switch.intfList(): #interface sorted by port num
            if intf.link:
                node1 = intf.link.intf1.node
                node2 = intf.link.intf2.node
                if(node1 == switch):
                    dest = node2
                    interface = intf.link.intf1 #get interface
                else:
                    dest = node1
                    interface = intf.link.intf2
                
                bandwidth = topo.linkInfo[switch.name][dest.name] #get the bandwidth of the link
                interface_name = interface.name
                create(interface_name, bandwidth)
    
    info('** Running CLI\n')
    CLI(net)

def stopNetwork():
    if net is not None:
        net.stop()
        # Remove QoS and Queues
        os.system('sudo ovs-vsctl --all destroy Qos')
        os.system('sudo ovs-vsctl --all destroy Queue')


if __name__ == '__main__':
    # Force cleanup on exit by registering a cleanup function
    atexit.register(stopNetwork)

    # Tell mininet to print useful information
    setLogLevel('info')
    startNetwork()
