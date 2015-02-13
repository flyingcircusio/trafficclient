# Copyright (c) 2008-2011 gocept gmbh & co. kg
# See also LICENSE.txt


from gocept.trafficclient.client import Client
import ZODB.DB
import ZODB.MappingStorage
import datetime
import gocept.trafficclient.client
import logging
import mocker
import re
import transaction
import unittest
import xmlrpclib


class TrafficClientInstanceTest(unittest.TestCase):

    def setUp(self):
        self.storage = ZODB.MappingStorage.MappingStorage()
        db = ZODB.DB(self.storage)
        self.connection = db.open()
        self.root = self.connection.root()

    def tearDown(self):
        transaction.abort()
        self.connection.close()
        self.storage.close()

    def test_empty_db_should_not_contain_gatherer(self):
        self.assertRaises(KeyError, self.root.__getitem__, 'client')

    def test_save_client_to_db(self):
        client = gocept.trafficclient.client.instance(self.root)
        self.assert_(isinstance(client, Client))
        self.assert_(client is self.root['client'])

    def test_instance_should_add_last_update_if_missing(self):
        client = gocept.trafficclient.client.instance(self.root)
        del client.last_update
        transaction.commit()
        client = gocept.trafficclient.client.instance(self.root)
        self.assertEqual(datetime.datetime.min, client.last_update)

    def test_instance_should_not_change_existing_last_update(self):
        client = gocept.trafficclient.client.instance(self.root)
        client.last_update = datetime.datetime.now()
        transaction.commit()
        client = gocept.trafficclient.client.instance(self.root)
        self.assertNotEqual(datetime.datetime.min, client.last_update)


class TrafficClientComputeTest(mocker.MockerTestCase):

    def setUp(self):
        self.client = Client()
        cls = self.mocker.patch(gocept.trafficclient.counter.Counter)
        cls._parse()
        self.mocker.result(185)
        self.mocker.count(2, 4)
        self.mocker.replay()
        self.fill_counters()

    def fill_counters(self):
        self.addrs = []
        self.counters = []
        for i in range(2):
            a = gocept.trafficclient.hostaddr.HostAddr("1.2.3.%i/16" % i)
            self.addrs.append(a)
            c = gocept.trafficclient.counter.Counter(a, ['eth0'], 100 * i)
            self.counters.append(c)
            self.client.savedcounters[a] = c

    def test_update_diffs(self):
        self.assertEquals([(self.addrs[0], 185), (self.addrs[1], 85)],
                          self.client._compute(self.addrs, ['eth0']))

    def test_compute_diffs_should_include_new_addrs(self):
        self.addrs.append(gocept.trafficclient.hostaddr.HostAddr("1.2.3.3/16"))
        self.assertEquals([(self.addrs[0], 185),
                           (self.addrs[1], 85),
                           (self.addrs[2], 0)],
                          self.client._compute(self.addrs, ['eth0']))

    def test_compute_should_update_savedcounters(self):
        self.client._compute(self.addrs, ['eth0'])
        expected = dict([
            (a, gocept.trafficclient.counter.Counter(a, ['eth0'], 185))
            for a in self.addrs])
        self.assertEquals(expected, self.client.savedcounters.data)

    def test_compute_should_not_generate_duplicate_keys(self):
        self.client._compute(self.addrs, ['eth0'])
        self.fill_counters()
        self.client._compute(self.addrs, ['eth0'])
        self.assertEquals(set(self.addrs),
                          set(self.client.savedcounters.keys()))


class TrafficClientUpdateTest(mocker.MockerTestCase):

    def setUp(self):
        self.client = Client()
        self.server = self.mocker.mock()

    def test_empty_update_should_connect_to_server(self):
        self.server.store(mocker.ANY, [])
        self.mocker.replay()
        self.client._update([], self.server)

    def test_update_converts_data(self):
        self.server.store(mocker.ANY, [('195.62.106.86', 1)])
        self.mocker.replay()
        hostaddr = gocept.trafficclient.hostaddr.HostAddr('195.62.106.86/27')
        self.client._update([(hostaddr, 1)], self.server)

    def test_avoids_xmlrpc_maxint(self):
        self.server.store(mocker.ANY, [('195.62.106.86', 2**31-1),
                                       ('195.62.106.86', 1)])
        self.mocker.replay()
        hostaddr = gocept.trafficclient.hostaddr.HostAddr('195.62.106.86/27')
        self.client._update([(hostaddr, 2**31)], self.server)

    def test_update_uses_correct_time_format(self):
        time = self.mocker.replace("time.time")
        time()
        self.mocker.result(1201684557.4)
        self.mocker.count(1, None)
        self.server.store(xmlrpclib.DateTime('20080130T10:15:57'), mocker.ANY)
        self.mocker.replay()
        self.client._update([], self.server)

    def test_updateerror_should_not_leak_password(self):
        self.server.store(mocker.ANY, mocker.ANY)
        self.mocker.throw(xmlrpclib.ProtocolError('admin:admin@localhost:8080',
                                                  404, "not found", ""))
        self.mocker.replay()
        try:
            self.client._update([], self.server)
        except Exception, e:
            self.assert_(not re.search(r'admin:admin', str(e)),
                         "Error message contains username and password")
            return
        self.fail("no exception raised")


class TrafficClientTransactionTest(mocker.MockerTestCase):

    def setUp(self):
        self.client = gocept.trafficclient.client.Client()
        self.client.savedcounters[1] = 2
        self.transaction = self.mocker.replace(transaction)

    def test_run_should_commit_and_set_last_update(self):
        self.transaction.commit()
        self.mocker.replay()
        self.client._run = lambda *args, **kw: None
        self.client.run(None, None, None, None)
        self.assertNotEqual(datetime.datetime.min, self.client.last_update)

    def test_exception_raised_should_abort_and_reraise(self):
        self.transaction.abort()
        self.mocker.replay()

        def provoke_error(*args, **kw):
            raise RuntimeError('provoked error')
        self.client._run = provoke_error
        self.assertRaises(
            Exception, lambda: self.client.run(
                None, None, None, datetime.datetime.now()))

    def test_last_update_within_grace_period_should_not_reraise(self):
        log = self.mocker.replace(logging.getLogger('trafficclient'))
        log.warning(mocker.ANY)
        self.transaction.abort()
        self.mocker.replay()

        def provoke_error(*args, **kw):
            raise xmlrpclib.Error()
        self.client._run = provoke_error
        last_update = datetime.datetime.now() - datetime.timedelta(minutes=10)
        self.client.last_update = last_update
        self.client.run(None, None, None, grace_period=60)
        self.assertEqual(last_update, self.client.last_update)

    def test_last_update_outside_grace_period_should_abort_and_reraise(self):
        self.transaction.abort()
        self.mocker.replay()

        def provoke_error(*args, **kw):
            raise xmlrpclib.Error()
        self.client._run = provoke_error
        last_update = datetime.datetime.now() - datetime.timedelta(minutes=10)
        self.client.last_update = last_update
        self.assertRaises(
            xmlrpclib.Error, lambda: self.client.run(
                None, None, None, grace_period=0))
        self.assertEqual(last_update, self.client.last_update)


class TrafficClientLogTest(mocker.MockerTestCase):

    def setUp(self):
        self.log = self.mocker.replace(logging.getLogger('trafficclient'))

    def test_log_format(self):
        self.log.info(
            'sending traffic ([195.62.106.86]=20) to http://server/uri')
        self.mocker.replay()

        hostaddr = gocept.trafficclient.hostaddr.HostAddr('195.62.106.86/27')
        Client()._log_traffic([(hostaddr, 20)], "http://server/uri")
