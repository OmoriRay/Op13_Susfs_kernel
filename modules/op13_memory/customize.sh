#!/system/bin/sh
SKIPUNZIP=0
[ "$BOOTMODE" = true ] || abort "Install from the BakaSU manager in Android"
[ "$(getprop ro.product.model)" = PJZ110 ] || abort "Expected PJZ110"
[ "$(getprop ro.product.device)" = OP5D0DL1 ] || abort "Expected OP5D0DL1"
[ "$(getprop ro.build.fingerprint)" = 'OnePlus/PJZ110/OP5D0DL1:17/CP2A.260605.016/V.487427a-2227f32-224bc4c:user/release-keys' ] || abort "ROM differs from audited target"
[ -x /system/bin/toybox ] || abort "System Toybox required"
/system/bin/toybox swapon --help 2>&1 | grep -q -- '-p' || abort "Toybox swapon priority support required"
[ -r /sys/block/zram0/comp_algorithm ] || abort "Built-in ZRAM required"
/system/bin/sh "$MODPATH/x1-handoff.sh" install || abort "X1 handoff failed; inspect /data/adb/op13_memory/handoff.log"
set_perm_recursive "$MODPATH" 0 0 0755 0644
for f in memory.sh x1-handoff.sh service.sh action.sh uninstall.sh; do set_perm "$MODPATH/$f" 0 0 0755; done
ui_print "OP13 Memory Companion installed. Reboot to apply."
if [ -f "$MODPATH/ab-install" ]; then
    mkdir -p /data/adb/op13_memory || abort "Cannot prepare A/B state"
    chmod 0700 /data/adb/op13_memory
    printf 'ab-stock\n' > /data/adb/op13_memory/profile.new || abort "Cannot save A/B baseline"
    mv -f /data/adb/op13_memory/profile.new /data/adb/op13_memory/profile || abort "Cannot activate A/B baseline"
    ui_print "Next boot: A/B baseline LZ4, 1x MemTotal, fixed reclaim parameters."
else
    ui_print "Default: LZ4, 2x MemTotal logical capacity, swappiness 100."
fi
ui_print "No live ZRAM reset was performed by this installer."
