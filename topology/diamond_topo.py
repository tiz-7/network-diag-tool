from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

def build_net():
    net = Mininet(controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    h1 = net.addHost('h1', ip='10.0.0.1/24')   # probe client
    h2 = net.addHost('h2', ip='10.0.0.2/24')   # probe server
    h3 = net.addHost('h3', ip='10.0.0.3/24')   # background traffic source
    h4 = net.addHost('h4', ip='10.0.0.4/24')   # background traffic sink
    s1, s2, s3, s4 = [net.addSwitch('s%d' % i, protocols='OpenFlow13') for i in range(1, 5)]
    net.addLink(h1, s1); net.addLink(h3, s1)
    net.addLink(h2, s4); net.addLink(h4, s4)
    net.addLink(s1, s2, bw=10, delay='5ms')              # Path A: fast
    net.addLink(s2, s4, bw=10, delay='5ms')
    net.addLink(s1, s3, bw=10, delay='20ms', loss=2)     # Path B: slow + lossy
    net.addLink(s3, s4, bw=10, delay='20ms')
    return net

if __name__ == '__main__':
    setLogLevel('info')
    net = build_net(); net.start(); CLI(net); net.stop()
