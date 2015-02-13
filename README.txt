Traffic gatherer
================

IPTables rules per host:

::

  iptables -A INPUT -s !$SUBNET -d $HOST
  iptables -A OUTPUT -s $HOST -d !$SUBNET
