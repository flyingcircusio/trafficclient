# See also LICENSE.txt

import ConfigParser
import os


def parse(fp):
    """Parse the config file and return values for serveruri and dbdir."""
    config = ConfigParser.SafeConfigParser()
    config.add_section('trafficclient')
    config.readfp(fp)
    dbdir = os.path.expanduser(config.get('trafficclient', 'dbdir'))
    try:
        os.stat(dbdir)
    except OSError:
        try:
            os.makedirs(dbdir)
        except OSError, e:
            raise RuntimeError("Cannot create dbdir '%s': %s" % (dbdir, e))
    location = config.get('trafficclient', 'location')
    if config.has_option('trafficclient', 'grace_period'):
        grace_period = config.getint('trafficclient', 'grace_period')
    else:
        grace_period = 60
    ignored_ips = set()
    if config.has_option('trafficclient', 'ignored-ips'):
        ignored_ips.update(
            x.strip() for x in
            config.get('trafficclient', 'ignored-ips').split('\n'))
    return (dbdir, location, grace_period, ignored_ips)
