{ pkgs ? import <nixpkgs> {} }:
  pkgs.mkShell {
    buildInputs = [ pkgs.python27Full pkgs.openldap pkgs.cyrus_sasl pkgs.libffi ];
    shellHook = ''
    	# https://github.com/NixOS/nixpkgs/issues/270
	    export SOURCE_DATE_EPOCH=315532800 # 1980
	    export PURE_PYTHON="1"
    	export CFLAGS="''${CFLAGS} -I${pkgs.cyrus_sasl.dev}/include/sasl -I${pkgs.libffi.dev}/include/ffi"
    	echo $CFLAGS
    	virtualenv --python=python2.7 .
    	bin/pip install zc.buildout
    	bin/buildout
    '';
}
