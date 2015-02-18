#!/usr/bin/env python
# Copyright (c) 2008 gocept gmbh & co. kg

import ZODB.DB
import ZODB.FileStorage.FileStorage
import datetime
import gocept.net.directory
import gocept.trafficclient.config
import gocept.trafficclient.counter
import gocept.trafficclient.hostaddr
import logging.handlers
import persistent
import persistent.dict
import re
import socket
import time
import transaction
import xmlrpclib
import sys


log = logging.getLogger('trafficclient')


class Client(persistent.Persistent):
    """Client for traffic analysis.

    Reads the byte addrs from all interfaces and puts deltas to the traffic
    analysis server.

    """

    def __init__(self):
        self.savedcounters = persistent.dict.PersistentDict()
        self.last_update = datetime.datetime.min

    def run(self, serveruri, location, upstream, grace_period):
        try:
            self._run(serveruri, location, upstream)
        except Exception, e:
            transaction.abort()
            grace_period = datetime.timedelta(minutes=grace_period)
            if self.last_update < datetime.datetime.now() - grace_period:
                raise e
            else:
                log.warning(
                    'An error occurred but last update is within'
                    ' grace period, ignoring: %s' % e)
        else:
            self.last_update = datetime.datetime.now()
            transaction.commit()

    def _run(self, serveruri, location, upstream):
        directory = gocept.net.directory.Directory()
        addrs = gocept.trafficclient.hostaddr.discover(directory, location)
        deltas = self._compute(addrs, upstream)
        trafficstore = xmlrpclib.ServerProxy(serveruri)
        self._log_traffic(deltas, serveruri)
        self._update(deltas, trafficstore)

    def _compute(self, addrs, upstream):
        """Compute the traffic deltas and update savedcounters."""
        deltas = []
        for c in [gocept.trafficclient.counter.Counter(a, upstream)
                  for a in addrs]:
            deltas.append(c.billable_diff(self.savedcounters.get(c.hostaddr)))
            self.savedcounters[c.hostaddr] = c
        return list(self.__process_deltas(deltas))

    def __process_deltas(self, deltas):
        # Turn deltas into a list of tuples (source_name, bytes)
        # Ensure that bytes is smaller than xmlrpclib.MAXINT
        for source, data in deltas:
            source = str(source.addr)
            while data > xmlrpclib.MAXINT:
                yield source, xmlrpclib.MAXINT
                data -= xmlrpclib.MAXINT
            if data:
                yield source, data

    def _update(self, deltas, store):
        """Send traffic deltas to trafficstore."""
        try:
            store.store_traffic(xmlrpclib.DateTime(time.time()), list(deltas))
        except (socket.error, xmlrpclib.Error), e:
            if hasattr(e, 'url'):
                e.url = re.sub(r'^.*@', '', e.url)
            raise e

    def _log_traffic(self, deltas, uri):
        msg = ["[%s]=%i" % (d[0], d[1]) for d in deltas]
        uri = re.sub(r'//.*@', '//', uri)
        log.info("sending traffic (%s) to %s" % (' '.join(msg), uri))


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
    config = gocept.trafficclient.config.parse(file(configfile))
    (serveruri, dbdir, location, upstream, grace_period) = config
    storage, connection = None, None
    try:
        storage = ZODB.FileStorage.FileStorage("%s/trafficclient.fs" % dbdir)
        database = ZODB.DB(storage)
        connection = database.open()
        client = instance(connection.root())
        client.run(serveruri, location, upstream, grace_period)
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
