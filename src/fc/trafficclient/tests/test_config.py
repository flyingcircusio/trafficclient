import fc.trafficclient.config
import StringIO
import pytest

# A configuration file consists of a single section and has keys for:

# * the XML-RPC URI of the traffic analysis server
# * the local directory where the last values are stored
# * the location identifier for which traffic should be gathered
# * the names of upstream interfaces
# * a grace period. If an error occurs, it will only be raised if the last
#   successfull update has been longer ago than this many minutes.
# This helps to
#   reduce noise in case the traffic server was just being restarted due to
#   logrotation and other such administrivia (optional, default 60 minutes)


def test_1():
    cfg = StringIO.StringIO("""
[trafficclient]
server = http://user:password@server:port/sources
dbdir = /tmp
location = whq
upstream = eth0,vdef0.0
grace_period = 15
ignored-ips = 1234.123.123.1
    213:12::0
    195.23.233.0
""")
    # Now, parse() reads the file and returns the values
    assert (fc.trafficclient.config.parse(cfg) ==
            ('/tmp', 'whq', 15,
             set(['1234.123.123.1', '195.23.233.0', '213:12::0'])))


def test_missing_options_raises_exception():
    with pytest.raises(Exception):
        fc.trafficclient.config.parse(StringIO.StringIO("""
[trafficclient]
dbdir = /tmp
    """))

    with pytest.raises(Exception):
        fc.config.parse(StringIO.StringIO("""
[trafficclient]
server = http://host/path
"""))

    # If the database directory does not exist and parse() fails to create it,
    # an exception is raised, too

    with pytest.raises(Exception):
        fc.config.parse(StringIO.StringIO("""
[trafficclient]
server = http://host/path
dbdir = /in/valid/path
"""))

    # If the directory contains a '~' it will be expanded:

    import os
    import pwd
    config = fc.trafficclient.config.parse(StringIO.StringIO(u"""
[trafficclient]
server =
dbdir = ~
location = test
"""))
    assert pwd.getpwuid(os.getuid())[5] == config[0]

    # The grace period is optional:

    assert (fc.trafficclient.config.parse(StringIO.StringIO("""
[trafficclient]
server = http://user:password@server:port/sources
dbdir = /tmp
location = whq
upstream = eth0,vdef0.0
    """)) ==
            ('/tmp',
             'whq',
             60,
             set([])))
