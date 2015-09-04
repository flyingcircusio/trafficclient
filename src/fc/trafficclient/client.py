#!/usr/bin/env python

import datetime
import fc.trafficclient.config
import gocept.net.directory
import IPy
import logging.handlers
import persistent
import persistent.dict
import re
import socket
import subprocess
import sys
import tempfile
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

    def __init__(self, persistent_client, serveruri, location, grace_period):
        self.persistent_client = persistent_client
        self.savedcounters = persistent_client.savedcounters
        self.serveruri = serveruri
        self.location = location
        self.grace_period = datetime.timedelta(minutes=grace_period)

        self.directory = gocept.net.directory.Directory()

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
        for network in self.directory.lookup_networks(self.location):
            self.networks.append(IPy.IP(network))

    def _fetch(self):
        output = tempfile.NamedTemporaryFile(delete=False)
        subprocess.check_call(
            ['pmacct', '-c', 'src_host,dst_host', '-M', '*,*', '-r'],
            stdout=output)
        return open(output.name, 'r')

    def fetch(self):
        """Update the saved byte counters."""
        with self._fetch() as out:
            for line in out.readlines():
                if not line.strip():
                    # The end of the tabular output is signalled by an
                    # empty line
                    break
                src_ip, dst_ip, packets, bytes = line.split()
                if src_ip == 'SRC_IP':
                    # First line
                    continue
                src_ip = IPy.IP(src_ip)
                dst_ip = IPy.IP(dst_ip)
                bytes = int(bytes)
                for net in self.networks:
                    if src_ip in net:
                        self.savedcounters.setdefault(str(src_ip), 0)
                        self.savedcounters[str(src_ip)] += bytes
                    if dst_ip in net:
                        self.savedcounters.setdefault(str(dst_ip), 0)
                        self.savedcounters[str(dst_ip)] += bytes

    def send(self):
        """Send traffic deltas to trafficstore."""
        if not self.savedcounters:
            return
        try:
            self.directory.store_traffic(
                xmlrpclib.DateTime(time.time()),
                list(self._convert_savedcounters_to_xmlrpc()))
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


def main(configfile):
    """Run the trafficclient script.

    The only argument configfile is the location of trafficclient's
    configuration file. If the configfile or required keys do not exist, an
    exception is raised.

    """
    configure_logging()
    config = fc.trafficclient.config.parse(file(configfile))
    (serveruri, dbdir, location, grace_period) = config
    storage, connection = None, None
    try:
        storage = ZODB.FileStorage.FileStorage("%s/trafficclient.fs" % dbdir)
        database = ZODB.DB(storage)
        connection = database.open()
        pclient = instance(connection.root())
        client = ClientRunner(pclient, serveruri, location, grace_period)
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
