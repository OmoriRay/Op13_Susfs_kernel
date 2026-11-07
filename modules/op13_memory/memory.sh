#!/system/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# No external config is sourced. Android calls use absolute Toybox paths so
# KernelSU/BakaSU BusyBox standalone dispatch cannot select the wrong applet.
set -u
ROOT=
if [ "${OP13MEM_TEST:-0}" = 1 ]; then
    case "${OP13MEM_TEST_ROOT:-}" in /tmp/op13mem-test-*) ROOT=$OP13MEM_TEST_ROOT;; *) exit 2;; esac
fi
MODDIR=${0%/*}
STATE="$ROOT/data/adb/op13_memory"
Z="$ROOT/sys/block/zram0"
P="$ROOT/proc"
TOYBOX="$ROOT/system/bin/toybox"
DEVICE="$ROOT/dev/block/zram0"
EXPECTED_FP='OnePlus/PJZ110/OP5D0DL1:17/CP2A.260605.016/V.487427a-2227f32-224bc4c:user/release-keys'
log() { printf '%s %s\n' "$(date +%s)" "$*" >> "$STATE/memory.log"; }
readval() { cat "$1" 2>/dev/null; }
prop() {
    if [ -n "$ROOT" ]; then readval "$ROOT/props/$1"; else /system/bin/getprop "$1"; fi
}
writeval() {
    # The injected writer exists only inside the isolated host-test filesystem.
    if [ -n "$ROOT" ]; then
        "$ROOT/write-node" "$2" "$1" 2>> "$STATE/memory.log"
    else
        { printf '%s\n' "$1" > "$2"; } 2>> "$STATE/memory.log"
    fi
    op13mem_write_rc=$?
    if [ "$op13mem_write_rc" -ne 0 ]; then log "WRITE failed: node=$2 value=$1 rc=$op13mem_write_rc"; fi
    return "$op13mem_write_rc"
}
# Android mksh deliberately uses 32-bit arithmetic, including numeric [ tests ].
# Byte capacities exceed that range. Keep all byte arithmetic/comparisons in
# awk; values here are bounded well below the exact-integer limit of doubles.
size_for_percent() { awk -v kb="$1" -v pct="$2" 'BEGIN {printf "%.0f\n", int(kb * 1024 * pct / 100 / 4096) * 4096}'; }
number_ge() { awk -v left="$1" -v right="$2" 'BEGIN {exit !(left + 0 >= right + 0)}'; }
current_algo() { sed -n 's/.*\[\([^]]*\)\].*/\1/p' "$Z/comp_algorithm"; }
supported() { tr '[]' '  ' < "$Z/comp_algorithm" | grep -qw "$1"; }
active() { awk '$1 ~ /\/zram0$/ {found=1} END{exit !found}' "$P/swaps"; }
swap_used() { awk '$1 ~ /\/zram0$/ {print $4;found=1;exit} END{if(!found) print 0}' "$P/swaps"; }
memval() { awk -v key="$1:" '$1==key {print $2;exit}' "$P/meminfo"; }
healthy_swap() {
    active && [ "$(memval SwapTotal)" -gt 0 ] &&
        awk '$1 ~ /\/zram0$/ && $3>0 {ok=1} END{exit !ok}' "$P/swaps"
}
set_status() {
    {
        printf 'state=%s\nprofile=%s\n' "$1" "${PROFILE:-unknown}"
        printf 'algorithm=%s\ndisksize=%s\n' "$(current_algo 2>/dev/null)" "$(readval "$Z/disksize")"
        printf 'SwapTotal_kB=%s\n' "$(memval SwapTotal)"
        printf 'boot_id=%s\n' "${BOOTID:-unknown}"
        printf 'requested_algorithm=%s\nrequested_bytes=%s\n' "${ALGO:-unknown}" "${TARGET_SIZE:-unknown}"
    } > "$STATE/status.new"
    mv -f "$STATE/status.new" "$STATE/status.txt"
    log "STATE $1"
}
check_target() {
    [ "$(prop ro.product.model)" = PJZ110 ] &&
    [ "$(prop ro.product.device)" = OP5D0DL1 ] &&
    [ "$(prop ro.build.fingerprint)" = "$EXPECTED_FP" ] || return 1
    if [ -n "$ROOT" ]; then release=$(readval "$ROOT/kernelrelease"); else release=$(uname -r); fi
    case "$release" in 6.6.*-android15-8-*-4k*) ;; *) return 1;; esac
    [ -x "$TOYBOX" ] && [ -r "$Z/comp_algorithm" ] || return 1
    "$TOYBOX" swapon --help 2>&1 | grep -q -- '-p' || return 1
    if [ -z "$ROOT" ]; then [ -b "$DEVICE" ] || return 1; fi
    for name in hummingbird_kernel haruhi_kernel; do
        dir="$ROOT/data/adb/modules/$name"
        if [ -f "$dir/module.prop" ] && [ ! -e "$dir/disable" ] && [ ! -e "$dir/remove" ]; then return 1; fi
    done
    for base in modules modules_update; do
        dir="$ROOT/data/adb/$base/ox_op13_kernel_manager"
        if [ -f "$dir/module.prop" ] && [ ! -e "$dir/disable" ] && [ ! -e "$dir/remove" ]; then
            [ "$(grep -c '^# OP13MEM_OWNER_BEGIN$' "$dir/ox/common.sh")" = 2 ] || return 1
        fi
    done
    # Preserve a configured UFS/backing device; this version does not own it.
    if [ -r "$Z/backing_dev" ]; then [ "$(readval "$Z/backing_dev")" = none ] || return 1; fi
}
configure_device() {
    # Caller has verified inactive swap and saved a recovery configuration.
    writeval 1 "$Z/reset" || return 1
    writeval "$1" "$Z/comp_algorithm" || return 1
    if [ "${AB_TEST:-0}" != 1 ] && [ "$1" = lz4 ] && [ -e "$Z/recomp_algorithm" ] && supported zstd; then
        writeval 'algo=zstd priority=1' "$Z/recomp_algorithm" || return 1
    fi
    writeval 0 "$Z/mem_limit" || return 1
    writeval "$2" "$Z/disksize" || return 1
    "$TOYBOX" mkswap "$DEVICE" >> "$STATE/memory.log" 2>&1 || return 1
    "$TOYBOX" swapon -p 32767 "$DEVICE" >> "$STATE/memory.log" 2>&1 || return 1
    healthy_swap
}
recover() {
    log 'Requested setup failed; recovering previous algorithm/capacity with swap enabled'
    # Never reset an active swap or one activated concurrently by Android.
    if active; then
        if healthy_swap; then set_status recovered-active; else set_status error-existing-swap; fi
        return 1
    fi
    recovery_algo=$OLD_ALGO
    recovery_size=$OLD_SIZE
    case "$recovery_algo" in lz4|zstd|lzo|lzo-rle|lz4hc) ;; *) recovery_algo=lz4;; esac
    # A refused reset can leave the old, still-formatted device intact. Try
    # reactivation before another reset; do not strand a working old header.
    if number_ge "$recovery_size" 1073741824 && [ "$(readval "$Z/disksize")" = "$recovery_size" ] && [ "$(current_algo)" = "$recovery_algo" ]; then
        if "$TOYBOX" swapon -p 32767 "$DEVICE" >> "$STATE/memory.log" 2>&1 && healthy_swap; then
            set_status recovered
            return 1
        fi
    fi
    if ! number_ge "$recovery_size" 1073741824; then
        recovery_size=$(size_for_percent "$MEM_KB" 75) || { set_status error-recovery-size; return 1; }
    fi
    log "RECOVERY algorithm=$recovery_algo bytes=$recovery_size"
    if configure_device "$recovery_algo" "$recovery_size"; then
        if number_ge "$OLD_LIMIT" 1; then writeval "$OLD_LIMIT" "$Z/mem_limit" || log 'Could not restore mem_limit'; fi
        set_status recovered
    else
        set_status error-no-swap
    fi
    return 1
}
tune() {
    partial=0
    for item in "sys/vm/swappiness:$SWAPPINESS" 'sys/vm/page-cluster:0' "sys/vm/watermark_scale_factor:$WATERMARK"; do
        node="$P/${item%:*}"; value=${item##*:}
        if [ -e "$node" ]; then
            printf '%s=%s\n' "${item%:*}" "$(readval "$node")" >> "$STATE/original-vm-$BOOTID.txt"
            if ! writeval "$value" "$node" || [ "$(readval "$node")" != "$value" ]; then partial=1; log "TUNE failed: $node"; fi
        else partial=1; log "TUNE missing: $node"; fi
    done
    node="$ROOT/sys/kernel/mm/lru_gen/min_ttl_ms"
    if [ -e "$node" ]; then
        printf 'min_ttl_ms=%s\n' "$(readval "$node")" >> "$STATE/original-vm-$BOOTID.txt"
        writeval 1000 "$node" || { partial=1; log 'min_ttl_ms write failed'; }
    fi
    [ "$partial" = 0 ]
}
boot() {
    mkdir -p "$STATE"; chmod 0700 "$STATE"
    PROFILE=$(readval "$STATE/profile" || true)
    [ -n "$PROFILE" ] || PROFILE=pandora_like
    AB_TEST=0
    case "$PROFILE" in
        pandora_like) ALGO=lz4; PERCENT=200; SWAPPINESS=100; WATERMARK=200;;
        density) ALGO=zstd; PERCENT=200; SWAPPINESS=100; WATERMARK=200;;
        game) ALGO=lz4; PERCENT=100; SWAPPINESS=60; WATERMARK=150;;
        ab-stock) ALGO=lz4; PERCENT=100; SWAPPINESS=100; WATERMARK=200; AB_TEST=1;;
        ab-lz4) ALGO=lz4-op13; PERCENT=100; SWAPPINESS=100; WATERMARK=200; AB_TEST=1;;
        ab-mid) ALGO=lz4mid-op13; PERCENT=100; SWAPPINESS=100; WATERMARK=200; AB_TEST=1;;
        *) log 'Unknown profile; no memory writes'; return 1;;
    esac
    BOOTID=$(readval "$P/sys/kernel/random/boot_id")
    case "$BOOTID" in ''|*[!a-zA-Z0-9-]*) log 'Invalid boot ID'; return 1;; esac
    mkdir "$STATE/lock-$BOOTID" 2>/dev/null || return 1
    trap 'rmdir "$STATE/lock-$BOOTID" 2>/dev/null || true' EXIT HUP INT TERM
    [ ! -f "$STATE/attempted-$BOOTID" ] || { log 'Already attempted this boot; no repeated reset'; return 0; }
    check_target || { set_status blocked-target-or-owner; return 1; }
    supported "$ALGO" || { set_status blocked-algorithm; return 1; }
    MEM_KB=$(memval MemTotal)
    case "$MEM_KB" in ''|*[!0-9]*) return 1;; esac
    [ "$MEM_KB" -ge 8000000 ] && [ "$MEM_KB" -le 40000000 ] || return 1
    TARGET_SIZE=$(size_for_percent "$MEM_KB" "$PERCENT") || { set_status blocked-capacity-calculation; return 1; }
    case "$TARGET_SIZE" in ''|*[!0-9]*) set_status blocked-capacity-calculation; return 1;; esac
    number_ge "$TARGET_SIZE" 1073741824 || { set_status blocked-capacity-calculation; return 1; }
    log "REQUEST profile=$PROFILE algorithm=$ALGO MemTotal_kB=$MEM_KB bytes=$TARGET_SIZE"
    OLD_ALGO=$(current_algo); OLD_SIZE=$(readval "$Z/disksize")
    OLD_LIMIT=$(awk '{print $4}' "$Z/mm_stat")
    case "$OLD_SIZE:$OLD_LIMIT" in *[!0-9:]*|:|*:|:*) return 1;; esac
    # Reject bind-masked tuning nodes instead of unmounting another controller.
    if awk '$5 ~ /^\/proc\/sys\/vm\/(swappiness|page-cluster|watermark_scale_factor)$/ {found=1} END{exit !found}' "$P/self/mountinfo"; then
        set_status blocked-masked-vm; return 1
    fi
    printf '%s %s %s\n' "$OLD_ALGO" "$OLD_SIZE" "$OLD_LIMIT" > "$STATE/recovery-$BOOTID.txt"
    : > "$STATE/attempted-$BOOTID"
    if active; then
        seconds=$(awk '{print int($1)}' "$P/uptime")
        used=$(swap_used); available=$(memval MemAvailable)
        if [ "$seconds" -gt 180 ] || [ "$used" -gt 65536 ] || [ "$available" -lt 2097152 ]; then
            log 'Active swap retained: outside early-boot/low-use window; requested capacity/algorithm deferred'
            healthy_swap || { set_status error-existing-swap; return 1; }
            if tune; then set_status adopted-existing; else set_status adopted-existing-partial; fi
            return 0
        fi
        # This is one bounded early-boot transition, never a game-mode toggle.
        "$TOYBOX" swapoff "$DEVICE" >> "$STATE/memory.log" 2>&1 || { set_status blocked-swapoff; return 1; }
        active && { set_status blocked-concurrent-owner; return 1; }
    fi
    # Recheck immediately before reset: a concurrent activator must not be reset.
    active && { set_status blocked-concurrent-owner; return 1; }
    configure_device "$ALGO" "$TARGET_SIZE" || { recover; return 1; }
    [ "$(current_algo)" = "$ALGO" ] && [ "$(readval "$Z/disksize")" = "$TARGET_SIZE" ] || { set_status error-profile-mismatch; return 1; }
    if tune; then set_status active; else set_status active-partial; fi
}
case "${1:-status}" in
    boot) boot;;
    status)
        [ ! -r "$STATE/status.txt" ] || cat "$STATE/status.txt"
        printf '\nLive swap:\n'; cat "$P/swaps"
        printf '\nLive ZRAM (algorithm, logical bytes, mm_stat):\n'
        cat "$Z/comp_algorithm" "$Z/disksize" "$Z/mm_stat"
        ;;
    profile)
        case "${2:-}" in pandora_like|density|game|ab-stock|ab-lz4|ab-mid) ;; *) echo 'Use profile pandora_like|density|game|ab-stock|ab-lz4|ab-mid'; exit 2;; esac
        mkdir -p "$STATE"; chmod 0700 "$STATE"
        printf '%s\n' "$2" > "$STATE/profile.new"
        mv -f "$STATE/profile.new" "$STATE/profile"
        echo 'Saved. Reboot to apply; no live swap reset.'
        ;;
    *) exit 2;;
esac
