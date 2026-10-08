#!/bin/sh
# Ship the embedded standard library as sourceless bytecode in Release builds.
#
# PythonNative prepares the runtime once per machine: the standard library
# is trimmed and compiled into __pycache__ (see
# pythonnative/project/runtime_assets.py). install_python copies it into
# the bundle; this step moves each compiled module to where its source was
# and deletes the source, the layout CPython imports without sources.
#
# Usage: PNFinalizePython.sh <bundle>/python/lib
set -e
LIB="$1"
[ -d "$LIB" ] || exit 0
find "$LIB" -path '*/__pycache__/*.pyc' -type f | while IFS= read -r compiled; do
    cache_dir=$(dirname "$compiled")
    package_dir=$(dirname "$cache_dir")
    name=$(basename "$compiled")
    module=${name%%.*}
    case "$name" in
        "$module".cpython-*.opt-*.pyc) rm -f "$compiled"; continue ;;
    esac
    if [ -f "$package_dir/$module.py" ]; then
        mv "$compiled" "$package_dir/$module.pyc"
        rm -f "$package_dir/$module.py"
    else
        rm -f "$compiled"
    fi
done
find "$LIB" -type d -name __pycache__ -empty -delete
