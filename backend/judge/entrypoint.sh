#!/bin/sh
# Prepare what isolate normally gets from systemd, then start the service.
set -e

mkdir -p /run/isolate/locks

CG=/sys/fs/cgroup
if [ -f "$CG/cgroup.controllers" ]; then
    # cgroup v2 forbids a cgroup from holding processes and delegating
    # controllers at once, so move ourselves aside before enabling them
    if [ ! -d "$CG/init" ]; then
        mkdir -p "$CG/init"
        while read -r pid; do
            echo "$pid" > "$CG/init/cgroup.procs" 2>/dev/null || true
        done < "$CG/cgroup.procs"
    fi
    for controller in cpu memory pids cpuset; do
        echo "+$controller" > "$CG/cgroup.subtree_control" 2>/dev/null || true
    done
    mkdir -p "$CG/isolate"
else
    echo "warning: no cgroup v2 at $CG, isolate will refuse to run" >&2
fi

exec "$@"
