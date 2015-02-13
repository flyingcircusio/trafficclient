# Copyright (c) 2010 gocept gmbh & co. kg
# See also LICENSE.txt

from gocept.trafficclient.hostaddr import HostAddr
import IPy
import gocept.trafficclient.hostaddr
import mocker


class HostAddrTest(mocker.MockerTestCase):

    def setUp(self):
        self.ha = HostAddr("195.62.106.86/27")

    def test_addr(self):
        self.assertEquals(IPy.IP('195.62.106.86'), self.ha.addr)

    def test_subnet(self):
        self.assertEquals(IPy.IP('195.62.106.64/27'), self.ha.subnet)

    def test_init_with_verbose_netmask(self):
        # IPy bug
        ipv6_verbose = '2001:638:906:1::db/ffff:ffff:ffff:ffff::'
        self.assert_(HostAddr(ipv6_verbose))

    def test_eq(self):
        self.assert_(HostAddr('195.62.106.86/27') ==
                     HostAddr('195.62.106.86/27'))

    def test_ne(self):
        self.assert_(HostAddr('195.62.106.86/27') !=
                     HostAddr('195.62.106.90/27'))

    def test_ne_netmask(self):
        self.assert_(HostAddr('195.62.106.86/26') !=
                     HostAddr('195.62.106.86/27'))


class FakeDirectory(object):

    def lookup_interfaces(self, node):
        return {'srv': [('195.62.106.125/27', None),
                         ('127.0.0.1/32', None)],
                'fe': [('2001:638:906:2:2e0:81ff:fe40:7768/64', None)],
                'sto': [('192.168.24.0/24', None)]}

    def list_nodes(self):
        return [{'parameters': {'location': 'whq'}, 'name': 'node1'},
                {'parameters': {'location': 'rzob'}, 'name': 'node2'}]


class DiscoverTest(mocker.MockerTestCase):

    def setUp(self):
        self.directory = FakeDirectory()

    def test_discover_returns_only_public_addresses(self):
        addresses = gocept.trafficclient.hostaddr.discover(
            self.directory, 'whq')
        self.assertEquals([
          HostAddr('195.62.106.125/27'),
        ], addresses)
