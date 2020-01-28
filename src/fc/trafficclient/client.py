#!/usr/bin/env python

import csv
import datetime
import fc.trafficclient.config
import glob
import gocept.net.directory
import IPy
import logging.handlers
import os
import persistent
import persistent.dict
import re
import socket
import sys
import time
import transaction
import xmlrpclib
import ZODB.DB
import ZODB.FileStorage.FileStorage


log = logging.getLogger('trafficclient')


class Client(persistent.Persistent):
    """Persistent object for storing client data

    Reads the byte addrs from all interfaces and puts deltas to the traffic
    analysis server.

    """

    def __init__(self):
        self.savedcounters = persistent.dict.PersistentDict()
        self.last_update = datetime.datetime.min


class ClientRunner(object):
    """Non-persistent, singleton to structure the update process."""

    SPOOL_PATTERN = "/var/spool/pmacctd/*.txt"

    def __init__(self, persistent_client, location, grace_period, ignored_ips):
        self.persistent_client = persistent_client
        self.savedcounters = persistent_client.savedcounters
        self.location = location
        self.grace_period = datetime.timedelta(minutes=grace_period)
        self.ignored_ips = ignored_ips

        self.directory = gocept.net.directory.Directory()

        self._local_ips = {}

    @property
    def last_update(self):
        return self.persistent_client.last_update

    def run(self):
        try:
            self._run()
        except Exception, e:
            transaction.abort()
            if (self.persistent_client.last_update <
                    datetime.datetime.now() - self.grace_period):
                raise
            else:
                log.warning(
                    'An error occurred but last update is within'
                    ' grace period, ignoring: %s' % e)
        else:
            self.persistent_client.last_update = datetime.datetime.now()
            transaction.commit()

    def _run(self):
        self.discover()
        self.fetch()
        self.log()
        self.send()

    def discover(self,):
        """Update the list of networks that belong to this location."""
        self.networks = []
        for vlan, nets in self.directory.lookup_networks(
                self.location).items():
            for network in nets:
                self.networks.append(IPy.IP(network))
        # Add ignored IPs here as well
        for ip in self.ignored_ips:
            # Those can be IP addresses without net, with net mask,
            # or host mask
            self.networks.append(IPy.IP(ip))

    def is_local_ip(self, ip):
        if ip not in self._local_ips:
            self._local_ips[ip] = False
            for net in self.networks:
                if ip in net:
                    self._local_ips[ip] = True
                    break
        return self._local_ips[ip]

    def _fetch(self):
        # A generator that returns a record for every line in every file.
        # When a file is consumed fully, it is deleted.
        # Matches the file format of pmacctd's csv print plugin:
        # TAG,TAG2,CLASS,SRC_MAC,DST_MAC,VLAN,COS,ETYPE,SRC_AS,DST_AS,BGP_COMMS,AS_PATH,PREF,MED,PEER_SRC_AS,PEER_DST_AS,PEER_SRC_IP,PEER_DST_IP,IN_IFACE,OUT_IFACE,MPLS_VPN_RD,SRC_IP,DST_IP,SRC_MASK,DST_MASK,SRC_PORT,DST_PORT,TCP_FLAGS,PROTOCOL,TOS,PACKETS,FLOWS,BYTES
        for spoolfile in glob.iglob(self.SPOOL_PATTERN):
            with open(spoolfile) as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if not row['SRC_IP'] or not row['DST_IP']:
                        continue
                    yield (IPy.IP(row['SRC_IP']),
                           IPy.IP(row['DST_IP']),
                           int(row['BYTES']))
            os.unlink(spoolfile)

    def fetch(self):
        """Gather all data from the spool directory."""
        for src, dst, bytes in self._fetch():
            if self.is_local_ip(src) and self.is_local_ip(dst):
                # Purely internal traffic. Ignore.
                continue
            elif self.is_local_ip(src):
                accounting_ip = src
            elif self.is_local_ip(dst):
                accounting_ip = dst
            else:
                # Purely external traffic. Should never happen, but hey:
                # don't break and dont account the wrong stuff.
                continue
            self.savedcounters.setdefault(str(accounting_ip), 0)
            self.savedcounters[str(accounting_ip)] += bytes

    def send(self):
        """Send traffic deltas to trafficstore."""
        if not self.savedcounters:
            return
        try:
            self.directory.store_traffic(
                xmlrpclib.DateTime(time.time()),
                list(self._convert_savedcounters_to_xmlrpc()))
            self.savedcounters.clear()
        except (socket.error, xmlrpclib.Error), e:
            if hasattr(e, 'url'):
                # Strip out passwords
                e.url = re.sub(r'^.*@', '', e.url)
            raise e

    def log(self):
        for src, value in sorted(self.savedcounters.items()):
            log.info("sending traffic: {} => {} bytes".format(src, value))

    def _convert_savedcounters_to_xmlrpc(self):
        # Turn deltas into a list of tuples (source_name, bytes)
        # Ensure that bytes is smaller than xmlrpclib.MAXINT
        for source, data in self.savedcounters.items():
            source = str(source)
            while data > xmlrpclib.MAXINT:
                yield source, xmlrpclib.MAXINT
                data -= xmlrpclib.MAXINT
            if data:
                yield source, data


def configure_logging():
    stderr = logging.StreamHandler()
    log.addHandler(stderr)
    log.setLevel(logging.INFO)


def _migrate_last_update(client):
    if not hasattr(client, 'last_update'):
        client.last_update = datetime.datetime.min
        transaction.commit()


def instance(dbroot):
    """Return the traffic client instance from the database or create a new
    one if there was none.
    """
    instance = dbroot.setdefault('client', Client())
    _migrate_last_update(instance)
    return instance


def main():
    """Run the trafficclient script.

    The only argument configfile is the location of trafficclient's
    configuration file. If the configfile or required keys do not exist, an
    exception is raised.

    """
    configfile = sys.argv[1]
    configure_logging()
    config = fc.trafficclient.config.parse(file(configfile))
    (dbdir, location, grace_period, ignored_ips) = config
    storage, connection = None, None
    try:
        storage = ZODB.FileStorage.FileStorage("%s/trafficclient.fs" % dbdir)
        database = ZODB.DB(storage)
        connection = database.open()
        pclient = instance(connection.root())
        client = ClientRunner(pclient, location, grace_period, ignored_ips)
        client.run()
        database.pack(None, 1)
    except Exception, e:
        log.exception(e)
        sys.exit(1)
    finally:
        transaction.abort()
        if connection:
            connection.close()
        if storage:
            storage.close()
