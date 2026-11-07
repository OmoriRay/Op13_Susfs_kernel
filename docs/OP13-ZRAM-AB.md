# OP13 ZRAM A/B test build

Experimental PJZ110 / exact reviewed ColorOS 17 firmware, android15-6.6 generation 8 / 4K.

This build adds privately namespaced upstream LZ4 1.10.0 (commit ebb370ca83af193212df4dcbadcc5d87bc0de2f0)
using legacy Crypto API backends `lz4-op13` and `lz4mid-op13` (MID level 2).
The original `lz4` stays available. The backend accepts full 4KB pages only.

Module profiles `ab-stock`, `ab-lz4`, `ab-mid` all use 100% of MemTotal logical capacity,
swappiness 100, page-cluster 0, watermark_scale_factor 200, MGLRU min_ttl_ms 1000.
The bundled installer saves `ab-stock` for the next boot. No automatic recompression worker.
Profile changes are deferred until reboot. Never reset active/busy ZRAM to force a test.

Verify the actual algorithm, capacity, `/proc/swaps`, module status, I/O errors and boot identity
before each measured run. A successful profile-save command is not a successful algorithm switch.
X1 ZRAM ownership handoff remains limited to the reviewed version; Scene and A-SOUL stay active.

Host userspace and codec sanitizer checks are preliminary evidence, not device boot/performance
verification. Existing kernel WARNINGs remain an unresolved limitation. Keep the full known-working
active-slot boot backup and module state backup before changing the test kernel/module.
No vendor_boot/init_boot/vbmeta writes, user data clearing, thermal unlocking or GPU changes are part
of this A/B build. AnyKernel3 still writes the reviewed active boot partition when actually installed.
