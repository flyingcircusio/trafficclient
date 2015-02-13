all:    libs

libs:   libwrap_uname.so

libwrap_uname.so: wrap_uname.c
	rm -f libwrap_uname.so*
	gcc -fPIC -shared -Wl,-soname,libwrap_uname.so.1 -ldl -o libwrap_uname.so.1.0  wrap_uname.c
	ln -s libwrap_uname.so.1.0 libwrap_uname.so.1
	ln -s libwrap_uname.so.1 libwrap_uname.so

clean:
	rm -f libwrap_uname.so*

# vim: set noet sts=8 ts=8:
