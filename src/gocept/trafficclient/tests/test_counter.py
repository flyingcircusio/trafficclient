# Copyright (c) 2010 gocept gmbh & co. kg
# See also LICENSE.txt

from gocept.trafficclient.counter import Counter, ReadError
import gocept.trafficclient.hostaddr
import mocker


class IPTablesTestStub(object):

    def _iptables_query(self):
        return """\
Chain INPUT (policy ACCEPT 4 packets, 1212 bytes)
    pkts      bytes target     prot opt in     out     source         destination
       2        3000         all  --  eth0      *      0.0.0.0/0    195.62.106.86
       1        611          all  --  eth0      *      0.0.0.0/0    195.62.106.75

Chain FORWARD (policy ACCEPT 0 packets, 0 bytes)
    pkts      bytes target     prot opt in     out     source         destination
       2        0             all  --  eth0      *      0.0.0.0/0    195.62.106.86
       1        0             all  --  eth0      *      0.0.0.0/0    195.62.106.75
       3        0             all  --  *      eth0       195.62.106.86 0.0.0.0/0
       4        0             all  --  *      eth0       195.62.106.75 0.0.0.0/0

Chain OUTPUT (policy ACCEPT 4 packets, 400 bytes)
    pkts      bytes target     prot opt in     out     source         destination
       3        4500         all  --  *      eth0       195.62.106.86 0.0.0.0/0
       4        5463         all  --  *      eth0       195.62.106.75 0.0.0.0/0
"""

    def _iptables_query_2_4(self):
        return """\
Chain INPUT (policy ACCEPT 132955 packets, 27535345 bytes)
    pkts      bytes target     prot opt in     out     source               destination
      44     0               0    --  eth0      *      0.0.0.0/0            195.62.106.86

Chain FORWARD (policy ACCEPT 0 packets, 0 bytes)
    pkts      bytes target     prot opt in     out     source               destination
      44     2994            0    --  eth0      *      0.0.0.0/0            195.62.106.86
      30     4778            0    --  *      eth0      195.62.106.86        0.0.0.0/0

Chain OUTPUT (policy ACCEPT 142782 packets, 20772791 bytes)
    pkts      bytes target     prot opt in     out     source               destination
      30     0              0    --  *      eth0      195.62.106.86        0.0.0.0/0
"""

    def _iptables_empty(self):
        return """\
Chain INPUT (policy ACCEPT)
target     prot opt source               destination

Chain FORWARD (policy ACCEPT)
target     prot opt source               destination

Chain OUTPUT (policy ACCEPT)
target     prot opt source               destination
"""


class CounterTest(mocker.MockerTestCase):

    def setUp(self):
        self.ha = gocept.trafficclient.hostaddr.HostAddr('195.62.106.86/27')

    def _setup_iptables(self, output):
        cls = self.mocker.patch(Counter)
        cls._iptables_query()
        self.mocker.count(1, 2)
        self.mocker.result(output)
        cls._reconfigure()
        self.mocker.count(0, 1)
        self.mocker.replay()

    def test_parse_simple(self):
        self._setup_iptables(IPTablesTestStub()._iptables_query())
        self.assertEquals(7500, Counter(self.ha, ['eth0']).value)

    def test_parse_2_4(self):
        self._setup_iptables(IPTablesTestStub()._iptables_query_2_4())
        self.assertEquals(7772, Counter(self.ha, ['eth0']).value)

    def test_parse_should_fail_on_wrong_subnet(self):
        self._setup_iptables("""\
       2        3000         all  --  *      *       195.62.106.86 !195.62.106.64/27
       3        4500         all  --  *      *       195.62.106.86 !195.62.106.0/27
""")
        self.assertRaises(ReadError, Counter, self.ha, ['eth0'])

    def test_parse_should_fail_on_wrong_proto(self):
        self._setup_iptables("""\
       2        3000         tcp  --  *      *       195.62.106.86 !195.62.106.64/27
       3        4500         all  --  *      *       195.62.106.86 !195.62.106.64/27
""")
        self.assertRaises(ReadError, Counter, self.ha, ['eth0'])

    def test_parse_should_fail_on_port_filters(self):
        self._setup_iptables("""\
       2        3000         all  --  *      *       195.62.106.86 !195.62.106.64/27 dpt:6969
       3        4500         all  --  *      *       195.62.106.86 !195.62.106.64/27
""")
        self.assertRaises(ReadError, Counter, self.ha, ['eth0'])

    def test_repr(self):
        self.assertEquals("Counter(HostAddr('195.62.106.86/27'), 1)",
                          repr(Counter(self.ha, ['eth0'], 1)))


class CounterConfigurationTest(mocker.MockerTestCase):

    def setUp(self):
        self.ha = gocept.trafficclient.hostaddr.HostAddr("195.62.106.75/27")
        self.iptables_effect = False

    def _mock_iptables(self, show_effect=True):
        cls = self.mocker.patch(Counter)
        cls._iptables_query()
        self.mocker.count(2)
        self.mocker.call(self._iptables_output)
        os = self.mocker.replace("os")
        os.system("iptables -D INPUT -i eth0 -d 195.62.106.75")
        self.mocker.result(1)
        os.system("iptables -A INPUT -i eth0 -d 195.62.106.75")
        self.mocker.result(0)
        os.system("iptables -D OUTPUT -o eth0 -s 195.62.106.75")
        self.mocker.result(1)
        os.system("iptables -A OUTPUT -o eth0 -s 195.62.106.75")
        self.mocker.result(0)
        os.system("iptables -D FORWARD -i eth0 -d 195.62.106.75")
        self.mocker.result(1)
        os.system("iptables -A FORWARD -i eth0 -d 195.62.106.75")
        self.mocker.result(0)
        os.system("iptables -D FORWARD -o eth0 -s 195.62.106.75")
        self.mocker.result(1)
        os.system("iptables -A FORWARD -o eth0 -s 195.62.106.75")
        self.mocker.result(0)
        if show_effect:
            self.mocker.call(self._put_iptables_into_effect)
        else:
            self.mocker.result(0)
        self.mocker.replay()

    def _iptables_output(self):
        if self.iptables_effect:
            return IPTablesTestStub()._iptables_query()
        else:
            return IPTablesTestStub()._iptables_empty()

    def _put_iptables_into_effect(self, *call_args):
        self.iptables_effect = True
        return 0

    def test_reconfigure_should_accept_one_failed_read(self):
        self._mock_iptables()
        self.assertEquals(6074, Counter(self.ha, ['eth0']).value)

    def test_reconfigure_should_die_on_second_failed_read(self):
        self._mock_iptables(False)
        self.assertRaises(ReadError, Counter, self.ha, ['eth0'])


class CounterMathTest(mocker.MockerTestCase):

    def setUp(self):
        self.mocker.patch(Counter)._parse()
        self.mocker.count(2)
        self.mocker.replay()
        self.ha = gocept.trafficclient.hostaddr.HostAddr("9.1.2.3/16")
        self.c1 = Counter(self.ha, ['eth0'])
        self.c2 = Counter(self.ha, ['eth0'])
        self.c1.value = 100
        self.c2.value = 100

    def test_equal(self):
        self.assert_(self.c1 == self.c2, 'counters fail on __eq__')

    def test_not_equal(self):
        self.assert_(not(self.c1 != self.c2), 'counters fail on __ne__')

    def test_not_equal_on_other_value(self):
        self.c2.value = 200
        self.assert_(self.c1 != self.c2, 'counters fail on __ne__')

    def test_not_equal_on_other_hostaddr(self):
        self.c2.hostaddr = gocept.trafficclient.hostaddr.HostAddr("9.1.2.3/24")
        try:
            self.c1 != self.c2
        except ArithmeticError:
            return
        self.fail("!= should raise exception")

    def test_diff_on_normal_counters_is_difference(self):
        self.c2.value = 101
        self.assertEquals((self.ha, 1), self.c2.billable_diff(self.c1))

    def test_diff_with_noncounter_should_fail(self):
        self.assertRaises(ArithmeticError, self.c2.billable_diff, "string")

    def test_diff_with_incompatible_hostaddr_should_fail(self):
        self.c2.hostaddr = gocept.trafficclient.hostaddr.HostAddr("9.7.3.1/16")
        self.assertRaises(ArithmeticError, self.c2.billable_diff, self.c1)

    def test_diff_should_be_zero_for_none(self):
        self.assertEquals((self.ha, 0), self.c2.billable_diff(None))

    def test_diff_should_be_new_value_on_wraparound(self):
        self.c2.value = 10
        self.assertEquals((self.ha, 10), self.c2.billable_diff(self.c1))
