# Copyright (c) 2010 gocept gmbh & co. kg
# See also LICENSE.txt

"""hostaddr is a single configured address on a host (a physical network device
or an alias device). The class HostAddr provides methods to configure and query
the traffic counter which can be attached to every address.

"""

import IPy
import re


class HostAddr(object):
    """Represents a configured address on one of the host's interfaces."""

    def __init__(self, ipaddr):
        """Create new HostAddr instace with ipaddr."""
        # bug in IPy, [gocept #63908]
        ipaddr = ipaddr.replace('/ffff:ffff:ffff:ffff::', '/64')
        self.addr = IPy.IP(ipaddr.split('/')[0])
        self.subnet = IPy.IP(ipaddr, make_net=True)

    def __repr__(self):
        return "HostAddr('%s/%s')" % (
            self.addr.strNormal(0), self.subnet.prefixlen())

    def __eq__(self, other):
        """Return true if self and other contain the same address and mask."""
        return isinstance(other, HostAddr) and (
            self.addr == other.addr and self.subnet == other.subnet)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        """Return a composite hash value from address and subnet."""
        return self.addr.__hash__() ^ self.subnet.__hash__()


def discover(directory, location):
    """Construct list of HostAddr objects from the directory.

    The directory is queried for all addresses on the srv and fe network on
    all nodes.

    """
    result = []
    for node in directory.list_nodes():
        if node['parameters']['location'] != location:
            continue
        for vlan, vlan_args in node['parameters']['interfaces'].items():
            for network, addresses in vlan_args['networks'].items():
                for addr in addresses:
                    addr = HostAddr(addr)
                    if addr.addr.version() != 4:
                        continue
                    if re.search(r'PUBLIC|PRIVATE', addr.addr.iptype()):
                        result.append(addr)
    return result
