# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt

"""Counter class with appropriate exceptions."""

import os
import re
import subprocess


class ConfigurationError(Exception):
    """Raised when HostAddr cannot configure iptables."""


class ReadError(Exception):
    """Raised when an iptables counter cannot be read."""


class Counter(object):
    """Represents a traffic counter with a counter reading.

    The value (counter reading) is retrieved in the constructor and stays
    constant for the whole object lifetime. For a new counter reading,
    instantiate a new object.

    """

    def __init__(self, hostaddr, upstream, value=None):
        """Create new Counter associated with a HostAddr and read it.

        If the reading is not possible, iptables is configured in such a way
        that traffic is counted from now. If neither the reading nor the
        iptables reconfiguration followed by a second reading attempt succeed,
        the constructor fails.

        """
        self.hostaddr = hostaddr
        self.value = value
        self.upstream = upstream
        if value is not None:
            return
        try:
            self.value = self._parse()
        except ReadError:
            self._reconfigure()
            self.value = self._parse()

    def billable_diff(self, old):
        """Compute a counter difference for billing.

        Return a tuple consisting of HostAddr and difference. Handle special
        cases like counter wraparound. If there is no old counter reading, we
        initialize the difference to 0, ignoring the current counter reading.

        """
        if old is None:
            return (self.hostaddr, 0)
        if self < old:
            return (self.hostaddr, self.value)
        return (self.hostaddr, self.value - old.value)

    def __cmp__(self, other):
        """Compare two Counter instances by value."""
        if not (isinstance(other, Counter) and self.hostaddr == other.hostaddr):
            raise ArithmeticError("Counter not comparable", self, other)
        return cmp(self.value, other.value)

    def __repr__(self):
        return "Counter(%r, %r)" % (self.hostaddr, self.value)

    def _parse(self):
        """Extract the sum of in and out traffic from iptables."""
        value = 0
        found = 0
        iptables_raw = self._iptables_query()
        addr = str(self.hostaddr.addr)
        # [0]pkts [1]bytes []target [2]prot [3]opt [4]in [5]out [6]src [7]dest
        for line in iptables_raw.splitlines():
            if not re.search(r'\d+\s+\d+\s+(all|0)\s+--', line):
                continue
            line = [x.strip() for x in line.split()]
            if len(line) != 8:
                continue
            pkts, bytes, prot, opt, in_, out, src, dest = line
            if ((out in self.upstream and src == addr) or
                (in_ in self.upstream and dest == addr)):
                value += int(bytes)
                found += 1
        if found != len(self.upstream) * 4:
            raise ReadError(
                "iptables gave unexpected number of traffic counters",
                iptables_raw)
        return value

    def _reconfigure(self):
        """(Re-)configure iptables to count non-locally originated/targeted
        traffic."""

        for dev in self.upstream:
            self._iptables_set('INPUT -i %s -d %s' %
                               (dev, self.hostaddr.addr))
            self._iptables_set('OUTPUT -o %s -s %s' %
                               (dev, self.hostaddr.addr))
            self._iptables_set('FORWARD -i %s -d %s' %
                               (dev, self.hostaddr.addr))
            self._iptables_set('FORWARD -o %s -s %s' %
                               (dev, self.hostaddr.addr))

    def _iptables_query(self):
        """Spawn iptables and returns the output."""
        return subprocess.Popen("iptables -nvx -L", shell=True,
                                stdout=subprocess.PIPE).communicate()[0]

    def _iptables_set(self, param):
        """Spawn iptables for reconfiguration and return exit code."""
        os.system('iptables -D ' + param)
        ret = os.system('iptables -A ' + param)
        if ret != 0:
            raise ConfigurationError("iptables -A %s failed with exitcode %i" %
                                     (param, ret))
        return ret
