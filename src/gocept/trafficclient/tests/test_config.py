# Copyright (c) 2011 gocept gmbh & co. kg
# See also LICENSE.txt

import doctest


def test_suite():
    return doctest.DocFileSuite(
        'configfile.txt',
        optionflags=(doctest.ELLIPSIS +doctest.NORMALIZE_WHITESPACE))
