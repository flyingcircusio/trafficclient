# Traffic Client Configuration File
# =================================

# First, we do some imports.

# >>> import fc.trafficclient.config
# >>> import StringIO

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

# >>> cfg = StringIO.StringIO("""
# ... [trafficclient]
# ... server = http://user:password@server:port/sources
# ... dbdir = /tmp
# ... location = whq
# ... upstream = eth0,vdef0.0
# ... grace_period = 15
# ... """)

# Now, parse() reads the file and returns the values

# >>> fc.trafficclient.config.parse(cfg)
# ('http://user:password@server:port/sources',
#  '/tmp',
#  'whq',
#  ['eth0', 'vdef0.0'],
#  15)

# If the server uri is missing, parse() raises an exception.

# >>> fc.trafficclient.config.parse(StringIO.StringIO("""
# ... [trafficclient]
# ... dbdir = /tmp
# ... """))
# Traceback (most recent call last):
# NoOptionError: No option 'server' in section: 'trafficclient'

# The same applies for a missing database directory:

# >>> fc.config.parse(StringIO.StringIO("""
# ... [trafficclient]
# ... server = http://host/path
# ... """))
# Traceback (most recent call last):
# NoOptionError: No option 'dbdir' in section: 'trafficclient'

# If the database directory does not exist and parse() fails to create it, an
# exception is raised.

# >>> fc.config.parse(StringIO.StringIO("""
# ... [trafficclient]
# ... server = http://host/path
# ... dbdir = /in/valid/path
# ... """))
# Traceback (most recent call last):
# RuntimeError: Cannot create dbdir '/in/valid/path': [Errno 13]
# Permission denied: '/in'

# If the directory contains a '~' it will be expanded:

# >>> import os, pwd
# >>> config = fc.config.parse(StringIO.StringIO(u"""
# ... [trafficclient]
# ... server =
# ... dbdir = ~
# ... location = test
# ... upstream = eth0
# ... """))
# >>> pwd.getpwuid(os.getuid())[5] == config[1]
# True

# The grace period is optional:

# >>> fc.config.parse(StringIO.StringIO("""
# ... [trafficclient]
# ... server = http://user:password@server:port/sources
# ... dbdir = /tmp
# ... location = whq
# ... upstream = eth0,vdef0.0
# ... """))
# ('http://user:password@server:port/sources',
#  '/tmp',
#  'whq',
#  ['eth0', 'vdef0.0'],
#  60)
