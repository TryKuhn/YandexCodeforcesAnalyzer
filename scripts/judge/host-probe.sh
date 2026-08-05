#!/usr/bin/env bash
# Host readiness probe for the judge sandbox (YCA-400 / #157).
#
# Run this ON THE PRODUCTION HOST (and inside the judge container once it exists)
# to confirm the environment can run isolate. Read-only: changes nothing.
#
#   ./scripts/judge/host-probe.sh            # human-readable report
#   ./scripts/judge/host-probe.sh --json     # machine-readable summary
#
# Exit code: 0 = ready, 1 = blocking problem found.

set -uo pipefail

JSON=0
[ "${1:-}" = "--json" ] && JSON=1

FAIL=0
WARN=0
RESULTS=""

# record <status> <key> <detail>
record() {
    local status="$1" key="$2" detail="$3"
    case "$status" in
        FAIL) FAIL=$((FAIL + 1)) ;;
        WARN) WARN=$((WARN + 1)) ;;
    esac
    RESULTS="${RESULTS}${status}\t${key}\t${detail}\n"
}

say() { [ "$JSON" -eq 0 ] && echo "$@"; }

say "=== judge host probe ==="
say ""

# --- where are we -----------------------------------------------------------
IN_CONTAINER=no
if [ -f /.dockerenv ] || grep -qE '(docker|containerd|kubepods)' /proc/1/cgroup 2>/dev/null; then
    IN_CONTAINER=yes
fi
record INFO context "in_container=${IN_CONTAINER} host=$(hostname 2>/dev/null || echo '?')"

# --- kernel -----------------------------------------------------------------
KERNEL=$(uname -r)
KMAJOR=${KERNEL%%.*}
KREST=${KERNEL#*.}
KMINOR=${KREST%%.*}
# isolate v2 wants a kernel with mature cgroup v2; 5.10 is the practical floor.
if [ "$KMAJOR" -gt 5 ] || { [ "$KMAJOR" -eq 5 ] && [ "$KMINOR" -ge 10 ]; }; then
    record OK kernel "$KERNEL"
else
    record FAIL kernel "$KERNEL (need >= 5.10 for reliable cgroup v2 memory accounting)"
fi

# --- cgroup layout ----------------------------------------------------------
CGTYPE=$(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo unknown)
case "$CGTYPE" in
    cgroup2fs)
        record OK cgroup_version "v2 unified (cgroup2fs)"
        ;;
    tmpfs)
        record FAIL cgroup_version "v1 or hybrid (tmpfs at /sys/fs/cgroup) - isolate v2 needs unified cgroup v2"
        ;;
    *)
        record FAIL cgroup_version "unknown ($CGTYPE)"
        ;;
esac

# --- cgroup controllers -----------------------------------------------------
if [ -r /sys/fs/cgroup/cgroup.controllers ]; then
    CTRL=$(cat /sys/fs/cgroup/cgroup.controllers)
    record INFO cgroup_controllers "$CTRL"
    for need in memory pids cpu cpuset; do
        if echo "$CTRL" | grep -qw "$need"; then
            record OK "controller_${need}" "available"
        else
            record FAIL "controller_${need}" "MISSING (required for mem/proc/cpu limits)"
        fi
    done
    # Delegation matters when the judge runs unprivileged inside a container.
    if [ -r /sys/fs/cgroup/cgroup.subtree_control ]; then
        record INFO cgroup_subtree_control "$(cat /sys/fs/cgroup/cgroup.subtree_control)"
    fi
    if [ -w /sys/fs/cgroup/cgroup.procs ]; then
        record OK cgroup_writable "/sys/fs/cgroup is writable (can create sub-cgroups)"
    else
        record WARN cgroup_writable "/sys/fs/cgroup NOT writable - isolate cannot create cgroups here"
    fi
else
    record FAIL cgroup_controllers "no /sys/fs/cgroup/cgroup.controllers (not cgroup v2)"
fi

# --- memory.swap: swap accounting must exist, and swap should be OFF ---------
if [ -e /sys/fs/cgroup/memory.swap.max ] || [ -e /sys/fs/cgroup/memory.swap.current ]; then
    record OK swap_accounting "cgroup v2 memory.swap.* present"
else
    record WARN swap_accounting "memory.swap.* not visible - swap accounting may be off"
fi

SWAPTOTAL=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
if [ "${SWAPTOTAL:-0}" -eq 0 ]; then
    record OK swap_off "swap disabled (good: swap makes TLE/MLE verdicts dishonest)"
else
    record WARN swap_off "swap ENABLED (${SWAPTOTAL} kB) - disable it on judging hosts"
fi

# --- privileges -------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
    record OK uid "running as root"
else
    record WARN uid "running as uid $(id -u) - isolate needs root or setuid install"
fi

if command -v capsh >/dev/null 2>&1; then
    # Only the "Current:" line counts. The "Bounding set" line lists caps the
    # process could ever gain, not the ones it holds - matching it says nothing.
    CUR=$(capsh --print 2>/dev/null | grep -m1 '^Current:' | cut -d: -f2- | tr -d ' ')
    record INFO capabilities "current=${CUR:-<none>}"
    if echo "$CUR" | grep -qE '(^|,)=[a-z]*ep|cap_sys_admin[^,]*\+[a-z]*e'; then
        record OK cap_sys_admin "present (needed to mount/manage namespaces)"
    else
        record WARN cap_sys_admin "absent - grant via cap_add or run the judge container privileged"
    fi
else
    record INFO capabilities "capsh not installed (apt install libcap2-bin) - cannot introspect"
fi

# --- init system ------------------------------------------------------------
INIT=$(ps -p 1 -o comm= 2>/dev/null || echo unknown)
if [ "$INIT" = "systemd" ]; then
    record OK init "systemd (isolate ships a systemd unit for its cgroup keeper)"
else
    record WARN init "$INIT - no systemd; isolate's cgroup keeper must be started manually"
fi

# --- user namespaces (relevant if we ever fall back to nsjail) --------------
if [ -r /proc/sys/kernel/unprivileged_userns_clone ]; then
    record INFO unprivileged_userns "$(cat /proc/sys/kernel/unprivileged_userns_clone)"
fi
if [ -r /proc/sys/user/max_user_namespaces ]; then
    record INFO max_user_namespaces "$(cat /proc/sys/user/max_user_namespaces)"
fi

# --- seccomp ----------------------------------------------------------------
if grep -q '^Seccomp:' /proc/self/status 2>/dev/null; then
    record INFO seccomp "mode=$(awk '/^Seccomp:/ {print $2}' /proc/self/status)"
fi

# --- sandbox tooling --------------------------------------------------------
if command -v isolate >/dev/null 2>&1; then
    record OK isolate "$(isolate --version 2>&1 | head -1)"
else
    record WARN isolate "not installed (expected on the host only if judging runs outside a container)"
fi
if command -v nsjail >/dev/null 2>&1; then
    record INFO nsjail "$(nsjail --help 2>&1 | head -1)"
fi

# --- compilers we must support ---------------------------------------------
if command -v g++ >/dev/null 2>&1; then
    record OK gpp "$(g++ --version | head -1)"
else
    record WARN gpp "g++ missing (needed for C++ solutions and testlib.h)"
fi
if command -v python3 >/dev/null 2>&1; then
    record OK python3 "$(python3 --version 2>&1)"
else
    record WARN python3 "python3 missing (needed for Python solutions)"
fi

# --- docker ----------------------------------------------------------------
if command -v docker >/dev/null 2>&1; then
    DINFO=$(docker info --format '{{.ServerVersion}}|{{.CgroupVersion}}|{{.CgroupDriver}}' 2>/dev/null)
    if [ -n "$DINFO" ]; then
        record INFO docker "version|cgroup|driver = $DINFO"
        case "$DINFO" in
            *"|2|"*) record OK docker_cgroup "docker reports cgroup v2" ;;
            *)       record FAIL docker_cgroup "docker is NOT on cgroup v2 ($DINFO)" ;;
        esac
    else
        record WARN docker "installed but daemon not reachable from here"
    fi
else
    record INFO docker "docker CLI not present (fine inside the judge container)"
fi

# --- timing stability (affects TLE fairness) -------------------------------
NCPU=$(nproc 2>/dev/null || echo '?')
record INFO cpu_count "$NCPU"
if [ -r /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    GOV=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)
    if [ "$GOV" = "performance" ]; then
        record OK cpu_governor "performance"
    else
        record WARN cpu_governor "$GOV - use 'performance' for reproducible time limits"
    fi
fi

# --- report -----------------------------------------------------------------
if [ "$JSON" -eq 1 ]; then
    printf '{\n  "fail": %d,\n  "warn": %d,\n  "checks": [\n' "$FAIL" "$WARN"
    first=1
    printf '%b' "$RESULTS" | while IFS=$'\t' read -r st key detail; do
        [ -z "${st:-}" ] && continue
        [ $first -eq 0 ] && printf ',\n'
        first=0
        esc=$(printf '%s' "$detail" | sed 's/\\/\\\\/g; s/"/\\"/g')
        printf '    {"status": "%s", "key": "%s", "detail": "%s"}' "$st" "$key" "$esc"
    done
    printf '\n  ]\n}\n'
else
    printf '%b' "$RESULTS" | while IFS=$'\t' read -r st key detail; do
        [ -z "${st:-}" ] && continue
        printf '%-5s %-24s %s\n' "$st" "$key" "$detail"
    done
    echo ""
    echo "=== summary: ${FAIL} blocking, ${WARN} warnings ==="
    if [ "$FAIL" -gt 0 ]; then
        echo "Host is NOT ready for the isolate-based sandbox. See FAIL lines above."
    else
        echo "No blocking problems found."
    fi
fi

[ "$FAIL" -gt 0 ] && exit 1
exit 0
