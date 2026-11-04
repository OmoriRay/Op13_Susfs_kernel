# OP13 BakaSU Extreme V2

Three explicit build profiles use the pinned 6.6.118 OEM base, BakaSU 35257/UAPI 6,
official SUSFS c7f670f5 with reviewed integration, LLVM 23.1.5, real O3,
configurable 64K anonymous mTHP, zsmalloc chain 16, LZ4-default ZRAM and enforcing CFI.

| Profile | LTO | HZ | ADIOS | Additional CPU tuning |
|---|---|---|---|---|
| extreme | Thin | 250 | existing 3.1.6 | unchanged |
| lab-full-lto | Full | 250 | existing 3.1.6 | unchanged |
| lab-max | Full | 1000 | 3.3.0 backport | experimental `-mtune=oryon-1` |

The source audit at Actions run 41858601891 found 130 files with conflicts when
integrating Linux 6.6.161 into this Android/OEM tree, plus missing/deleted-path
differences. That integration is **not included** in these 6.6.118 packages.
No profile changes SUBLEVEL to claim an unmerged LTS update.

SUSFS native SELinux hooks/selinuxfs/services/status sections are excluded as a
group; BakaSU supplies its own SELinux hiding implementation. The priority UID
command is explicitly connected to the new SUSFS implementation. The matching
upstream ARM64 helper is supplied separately, without automatic installation.
The `smap_gather_stats` filter covers all gather callers while preserving the
original rollup cursor/locking flow.

The ADIOS backport replaces only the existing scheduler implementation. It is
derived from firelzrd/adios commit 6fa79e32d9a33a0d671b108074aca2b5df9cd967,
patches/stable/0001-linux6.12.44-ADIOS-3.3.0.patch; the base tree already supplies
the scheduler Kconfig, Makefile and elevator integration. Upstream authors and
licenses are preserved.
The rotational-device test uses the 6.6 `!blk_queue_nonrot(q)` equivalent of the
newer `BLK_FEAT_ROTATIONAL` queue-limits feature.

LLVM 23 enables `__counted_by`, unlike the original LLVM 18 build. Legacy
genksyms includes this non-layout annotation in type hashes. The compatibility
patch excludes it only under `__GENKSYMS__`, retaining normal compiler bounds
instrumentation. Four interconnect CRCs are checked before the full build,
followed by all sampled vendor imports before packaging.

Existing WALT/HMBIRD/slim_walt interfaces remain available. This build does not
force their runtime activation or add a frequency/affinity controller. Scene EP
and A-SOUL remain the intended user environment. PGO, proprietary KFAS/hybrid
compression and new GPU/DDR OPPs are not claimed as implemented.

Artifacts are experimental, not boot-tested or performance-validated. They
include final config, source/patch locks, real compiler-command checks, ELF and
symbol evidence, hashes and a narrowly guarded AK3 ZIP for the reviewed PJZ110
ColorOS 17 target/slot. No release publishing or device flashing is automated.
