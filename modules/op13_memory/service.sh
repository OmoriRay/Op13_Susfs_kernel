#!/system/bin/sh
MODDIR=${0%/*}
# Bounded wait; a module must not block boot or repeatedly reset live swap.
n=0
until [ "$(/system/bin/getprop sys.boot_completed)" = 1 ]; do
    n=$((n + 1))
    [ "$n" -le 120 ] || exit 1
    sleep 1
done
sleep 8
/system/bin/sh "$MODDIR/memory.sh" boot
