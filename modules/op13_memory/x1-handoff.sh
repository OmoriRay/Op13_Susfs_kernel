#!/system/bin/sh
set -eu
ROOT=
if [ "${OP13MEM_TEST:-0}" = 1 ]; then
    case "${OP13MEM_TEST_ROOT:-}" in /tmp/op13mem-test-*) ROOT=$OP13MEM_TEST_ROOT;; *) exit 2;; esac
fi
STATE="$ROOT/data/adb/op13_memory"
mkdir -p "$STATE"
chmod 0700 "$STATE"
for base in modules modules_update; do
    dir="$ROOT/data/adb/$base/ox_op13_kernel_manager"
    file="$dir/ox/common.sh"
    [ -f "$dir/module.prop" ] || continue
    [ ! -L "$file" ] || { echo 'Refuse symlink common.sh' >> "$STATE/handoff.log"; exit 1; }
    [ -f "$file" ] || exit 1
    tmp="$file.op13mem.$$"
    trap 'rm -f "$tmp"' EXIT HUP INT TERM
    # Our block is intentionally inert whenever the companion is disabled or
    # removed. X1 hiding, integrity, charging and CPU functions are untouched.
    if [ "${1:-}" = install ]; then
        grep -q '^version=2\.13\.0$' "$dir/module.prop" || { echo 'Unreviewed X1 version' >> "$STATE/handoff.log"; exit 1; }
        guards=$(grep -c '^# OP13MEM_OWNER_BEGIN$' "$file" || true)
        [ "$guards" = 2 ] && continue
        [ "$guards" = 0 ] || exit 1
        count=$(grep -Ec '^(zram_apply|ram_expand_apply)\(\) \{$' "$file")
        [ "$count" = 2 ] || exit 1
        cp -p "$file" "$STATE/x1-$base-original-$(date +%s)-$$.sh"
        awk '
            {print}
            /^(zram_apply|ram_expand_apply)\(\) \{$/ {
                print "# OP13MEM_OWNER_BEGIN"
                print "  if [ -f /data/adb/modules/op13_memory/module.prop ] && [ ! -e /data/adb/modules/op13_memory/disable ] && [ ! -e /data/adb/modules/op13_memory/remove ]; then"
                print "    return 0"
                print "  fi"
                print "# OP13MEM_OWNER_END"
            }
        ' "$file" > "$tmp"
    elif [ "${1:-}" = remove ]; then
        awk '/^# OP13MEM_OWNER_BEGIN$/{skip=1;next} /^# OP13MEM_OWNER_END$/{skip=0;next} !skip{print}' "$file" > "$tmp"
    else
        exit 2
    fi
    # Validate before atomic replacement; source backups are never executed.
    sh -n "$tmp"
    chmod 0644 "$tmp"
    if [ -z "$ROOT" ]; then chown 0:0 "$tmp"; fi
    mv -f "$tmp" "$file"
    echo "$(date +%s) ${1:-} $base: guarded only zram_apply and ram_expand_apply" >> "$STATE/handoff.log"
    trap - EXIT HUP INT TERM
done
