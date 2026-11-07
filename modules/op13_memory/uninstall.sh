#!/system/bin/sh
# Remove only our guarded insertions. Never replace a newer X1 common.sh
# wholesale, and do not swapoff/reset live ZRAM while uninstalling.
/system/bin/sh "${0%/*}/x1-handoff.sh" remove
