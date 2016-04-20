from fc.trafficclient.client import Client, ClientRunner
import datetime
import fc.trafficclient.client
import glob
import IPy
import mock
import os.path
import pytest
import shutil
import transaction
import xmlrpclib
import ZODB.DB
import ZODB.MappingStorage


@pytest.yield_fixture
def database():
    storage = ZODB.MappingStorage.MappingStorage()
    db = ZODB.DB(storage)
    connection = db.open()
    root = connection.root()

    yield root

    transaction.abort()
    connection.close()
    storage.close()


@pytest.fixture
def client(database, directory, tmpdir):
    pclient = fc.trafficclient.client.instance(database)

    shutil.copytree(os.path.dirname(__file__) + '/logs',
                    str(tmpdir) + '/pmacctd')

    client = ClientRunner(pclient, 'test', 1, set(['141.1.1.1']))
    client.SPOOL_PATTERN = str(tmpdir) + '/pmacctd/*.txt'
    return client


@pytest.fixture
def directory(monkeypatch):
    import gocept.net.directory
    d = mock.Mock()
    monkeypatch.setattr(gocept.net.directory, 'Directory', d)
    d = d()
    d.lookup_networks.return_value = {'stb': ['195.62.126.0/24']}
    return d


def test_empty_db_should_not_contain_gatherer(database):
    with pytest.raises(KeyError):
        database['client']


def test_save_client_to_db(database):
    client = fc.trafficclient.client.instance(database)
    assert isinstance(client, Client)
    assert client is database['client']


def test_instance_should_add_last_update_if_missing(database):
    client = fc.trafficclient.client.instance(database)
    del client.last_update
    transaction.commit()
    client = fc.trafficclient.client.instance(database)
    assert datetime.datetime.min == client.last_update


def test_instance_should_not_change_existing_last_update(database):
    client = fc.trafficclient.client.instance(database)
    client.last_update = datetime.datetime.now()
    transaction.commit()
    client = fc.trafficclient.client.instance(database)
    assert client.last_update != datetime.datetime.min


def test_fetch(client):
    client.networks = [IPy.IP('172.20.2.0/24'),
                       IPy.IP('2a02:238:f030:1c2::/64'),
                       IPy.IP('172.30.3.0/24'),
                       IPy.IP('2a02:238:f030:1c3::/64')]
    client.fetch()
    assert client.savedcounters == {
        '2a02:238:f030:1c2::13': 1296,
        '2a02:238:f030:1c3::19': 2216,
        '2a02:238:f030:1c3::104c': 504,
        '2a02:238:f030:1c3::106c': 2104,
        '2a02:238:f030:1c3::c': 1568,
        '2a02:238:f030:1c2::53': 288,
        '2a02:238:f030:1c3::1076': 1072,
        '2a02:238:f030:1c3::53': 1568,
        '2a02:238:f030:1c3::1059': 6640,
        '2a02:238:f030:1c3::1080': 2792,
        '2a02:238:f030:1c2::c': 72,
        '2a02:238:f030:1c2::b': 72,
        '172.20.2.44': 9240,
        '2a02:238:f030:1c3::8': 1280,
        '2a02:238:f030:1c3::9': 1360,
        '2a02:238:f030:1c3::1082': 1856,
        '2a02:238:f030:1c3::1087': 7256,
        '2a02:238:f030:1c3::1': 1776,
        '2a02:238:f030:1c3::3': 2872,
        '2a02:238:f030:1c3::4': 1707552,
        '2a02:238:f030:1c3::5': 1136,
        '2a02:238:f030:1c3::6': 1280,
        '2a02:238:f030:1c3::7': 1216,
        '2a02:238:f030:1c3::107e': 1488,
        '2a02:238:f030:1c3::107d': 1000,
        '2a02:238:f030:1c3::1e': 1864,
        '2a02:238:f030:1c2::105d': 72,
        '2a02:238:f030:1c3::1060': 2648,
        '2a02:238:f030:1c3::1007': 648,
        '2a02:238:f030:1c3::12': 5952,
        '2a02:238:f030:1c3::13': 8048,
        '2a02:238:f030:1c3::10': 1720,
        '2a02:238:f030:1c3::a': 1424,
        '2a02:238:f030:1c3::b': 1784,
        '172.30.3.3': 1824,
        '2a02:238:f030:1c3::e': 1888,
        '2a02:238:f030:1c3::f': 1360,
        '2a02:238:f030:1c2::6': 72,
        '2a02:238:f030:1c2::1007': 72,
        '2a02:238:f030:1c3::1075': 1288,
        '2a02:238:f030:1c2::1066': 72,
        '2a02:238:f030:1c2::8': 72}
    assert glob.glob(client.SPOOL_PATTERN) == []


def test_empty_update_should_connect_to_server(client, directory):
    client.send()
    assert not directory.store_traffic.call_count


def test_avoids_xmlrpc_maxint(client):
    client.savedcounters['195.62.106.86'] = 2 ** 31 - 1
    client.savedcounters['195.62.106.88'] = 1
    client.savedcounters['195.62.106.89'] = 2 ** 32
    assert list(client._convert_savedcounters_to_xmlrpc()) == [
        ('195.62.106.86', 2147483647),
        ('195.62.106.89', 2147483647L),
        ('195.62.106.89', 2147483647L),
        ('195.62.106.89', 2L),
        ('195.62.106.88', 1)]


def test_updateerror_should_not_leak_password(client, directory):
    client.savedcounters['127.0.01'] = 12

    def error(time, data):
        raise xmlrpclib.ProtocolError(
            'admin:admin@localhost:8080', 404, "not found", "")
    directory.store_traffic.side_effect = error
    with pytest.raises(xmlrpclib.ProtocolError) as e:
        client.send()
    assert repr(e.value) == '<ProtocolError for localhost:8080: 404 not found>'


def test_run_should_commit_and_set_last_update(client):
    client.savedcounters['127.0.0.1'] = 100
    client.run()
    assert client.persistent_client.last_update != datetime.datetime.min
    assert client.savedcounters == {}


def test_exception_raised_should_abort_and_reraise(client):
    client.savedcounters['127.0.0.1'] = 100

    def provoke_error(*args, **kw):
        raise RuntimeError('provoked error')
    client._run = provoke_error
    with pytest.raises(RuntimeError):
        client.run()


def test_last_update_within_grace_period_should_not_reraise(client):
    def provoke_error(*args, **kw):
        raise xmlrpclib.Error()
    client._run = provoke_error
    client.grace_period = datetime.timedelta(minutes=20)
    last_update = datetime.datetime.now() - datetime.timedelta(minutes=10)
    client.persistent_client.last_update = last_update
    client.run()
    assert client.last_update == last_update


def test_last_update_outside_grace_period_should_abort_and_reraise(client):
    def provoke_error(*args, **kw):
        raise xmlrpclib.Error()
    client._run = provoke_error
    client.grace_period = datetime.timedelta(minutes=5)
    last_update = datetime.datetime.now() - datetime.timedelta(minutes=10)
    client.persistent_client.last_update = last_update
    with pytest.raises(Exception):
        client.run()
    assert client.last_update == last_update


@pytest.fixture
def logger(monkeypatch):
    class Logger(object):
        def __getattr__(self, name):
            return lambda *args: log.append(*args)
    log = []
    monkeypatch.setattr(fc.trafficclient.client, 'log', Logger())
    return log


def test_log_format(logger, client):
    client.savedcounters['195.62.106.86/27'] = 100
    client.log()
    assert ['sending traffic: 195.62.106.86/27 => 100 bytes'] == logger
