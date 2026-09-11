#!/bin/bash

# `mkp package` reinstalls the package into the site afterward, which copies
# the plugin files into local/lib/python3/cmk_addons/plugins/<pkg>/ as real
# files, clobbering the per-file symlinks symlink.sh sets up. Re-run it here
# so every build packages the current workspace source, not a stale copy
# left over from the previous build's reinstall step.
"$(dirname "$0")/symlink.sh"

NAME=$(python3 -c 'print(eval(open("package").read())["name"])')
VERSION=$(python3 -c 'print(eval(open("package").read())["version"])')
rm /omd/sites/cmk/var/check_mk/packages/${NAME} \
   /omd/sites/cmk/var/check_mk/packages_local/${NAME}-*.mkp ||:

mkp -v package package 2>&1 | sed '/Installing$/Q' ||:

cp /omd/sites/cmk/var/check_mk/packages_local/$NAME-$VERSION.mkp .

mkp inspect $NAME-$VERSION.mkp

# The reinstall above just clobbered the symlinks again (same reason as
# above). Re-run so the local dev site keeps reflecting live workspace
# edits for testing, instead of the frozen copy from this build.
"$(dirname "$0")/symlink.sh"
