from fc.trafficclient.client import Client, ClientRunner
import datetime
import fc.trafficclient.client
import IPy
import mock
import os.path
import pytest
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
def client(database, directory, monkeypatch):
    pclient = fc.trafficclient.client.instance(database)

    def _fetch(self, interface):
        return open(os.path.dirname(__file__) + '/sample.pmacct',
                    'rb')

    monkeypatch.setattr(
        fc.trafficclient.client.ClientRunner, '_fetch', _fetch)
    return ClientRunner(pclient, 'test', 1)


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
    client.networks = [IPy.IP('195.62.126.0/24')]
    client.fetch('ethtr')
    assert client.savedcounters == {
        '195.62.126.104': 3465,
        '195.62.126.110': 44554,
        '195.62.126.111': 10963,
        '195.62.126.119': 17426,
        '195.62.126.122': 77979,
        '195.62.126.13': 44,
        '195.62.126.16': 8524,
        '195.62.126.18': 31743,
        '195.62.126.24': 15503,
        '195.62.126.26': 149415,
        '195.62.126.32': 10490,
        '195.62.126.33': 229595,
        '195.62.126.43': 569124,
        '195.62.126.44': 11930,
        '195.62.126.48': 342,
        '195.62.126.51': 5496,
        '195.62.126.60': 1336}
    # Normally the pmacct resets the counter. If we fetch the second
    # time our counters increase.
    client.fetch('ethtr')
    assert client.savedcounters == {
        '195.62.126.104': 6930,
        '195.62.126.110': 89108,
        '195.62.126.111': 21926,
        '195.62.126.119': 34852,
        '195.62.126.122': 155958,
        '195.62.126.13': 88,
        '195.62.126.16': 17048,
        '195.62.126.18': 63486,
        '195.62.126.24': 31006,
        '195.62.126.26': 298830,
        '195.62.126.32': 20980,
        '195.62.126.33': 459190,
        '195.62.126.43': 1138248,
        '195.62.126.44': 23860,
        '195.62.126.48': 684,
        '195.62.126.51': 10992,
        '195.62.126.60': 2672}


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
