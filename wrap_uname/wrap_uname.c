/*
 * uname() wrapper
 *
 * To run, use something like 
 * LD_PRELOAD=$PWD/wrap_uname/libwrap_uname.so ./bin/buildout
 * modelled after 
 * <http://scaryreasoner.wordpress.com/2007/11/17/using-ld_preload-libraries-and-glibc-backtrace-function-for-debugging/>.
 * Written by Christian Kauhaus <kc@gocept.com>.
 * Copyright (c) 2008 gocept gmbh & co. kg.
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/utsname.h>
#include <string.h>

static int (*next_uname)(struct utsname *name) = NULL;

/*
 * Wrapper for uname. The wrapper installs itself when called for the first
 * time. Then, it modifies the machine string returned by uname() calls to
 * prevent setuptools loading possibly incompatible binary eggs. To accomplish
 * this, the machine is changed from 'i686' to 'i386' for which only few binary
 * eggs exist.
 */
int uname(struct utsname *name)
{
        char *msg;
        int rc;

        if (next_uname == NULL) {
                // next_uname = dlsym((void *) -11, /* RTLD_NEXT, */ "uname");
                next_uname = dlsym(RTLD_NEXT, "uname");
                if ((msg = dlerror()) != NULL) {
                        fprintf(stderr, "uname: dlopen failed: %s\n", msg);
                        fflush(stderr);
                        exit(1);
                }
        }
        rc = next_uname(name);
        if (0 == strcmp("i686", name->machine))
            name->machine[1] = '3';
        return rc;
}
