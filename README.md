<!--
  Op13_Susfs_kernel — README
  Repo: ox1d3x3/Op13_Susfs_kernel
  README revision: 2026-10-18 (ColorOS 17 / Android 17 · SukiSU Ultra v114 · BakaSU v111)
-->

## BakaSU Extreme V2 实验构建

本分支新增独立的 [Extreme V2 工作流](../../actions/workflows/Build_BakaSU_Extreme.yml)。
共同配置为 BakaSU 35257 / UAPI 6、SUSFS c7f670f5 适配、LLVM 23.1.5、真实 O3、
可配置 64K mTHP、zsmalloc chain 16、LZ4 默认 ZRAM 和 enforcing CFI。

| 版本 | LTO | HZ | ADIOS | 额外调优 |
|---|---|---|---|---|
| extreme | Thin | 250 | 3.1.6 | 主候选 |
| lab-full-lto | Full | 250 | 3.1.6 | Full LTO 对照 |
| lab-max | Full | 1000 | 3.3.0 回移 | 实验性 `-mtune=oryon-1` |

**这些包的真实 OEM 底座为 6.6.118。** 6.6.161 预审发现 130 个文件发生合并冲突，
因此没有纳入这些构建，也没有修改版本号冒充完成升级。
保留 Scene EP / A-SOUL 使用环境，不自动增加频率控制器、安装调优模块或刷写手机。
构建通过、样本 CRC 匹配均不等于实机启动、完整 ABI 或游戏性能已经验证。
详细来源、补丁和限制见 [制作说明](scripts/extreme/README.md)。

<h1 align="center">If This Kernel is useful to you, a ⭐ helps others find it.</h1>

<div align="center">

<img src="./.github/assets/hero.svg" alt="OP13 GKI Kernel banner — OnePlus 13, Android 17, BakaSU and SukiSU Ultra with SUSFS" width="100%" />

<br/>

<!-- Build lanes -->
<a href="../../actions/workflows/Build_ReSukiSU.yml">
  <img alt="BakaSU build" src="https://img.shields.io/badge/build-BakaSU%20v111-0A84FF?style=flat-square&logo=github" />
</a>
<a href="../../actions/workflows/Build%20SukiSU_Ultra.yml">
  <img alt="SukiSU Ultra build" src="https://img.shields.io/badge/build-SukiSU%20Ultra%20v114-0A84FF?style=flat-square&logo=github" />
</a>

<br/>

<a href="../../releases">
  <img alt="Release" src="https://img.shields.io/github/v/release/ox1d3x3/Op13_Susfs_kernel?display_name=tag&sort=date&style=flat-square&label=Release&logo=github" />
</a>
<a href="../../releases">
  <img alt="Downloads" src="https://img.shields.io/github/downloads/ox1d3x3/Op13_Susfs_kernel/total?style=flat-square&label=Downloads&logo=github" />
</a>
<a href="../../commits">
  <img alt="Last Commit" src="https://img.shields.io/github/last-commit/ox1d3x3/Op13_Susfs_kernel?style=flat-square&label=Last%20Commit&logo=git" />
</a>
<img alt="License" src="https://img.shields.io/badge/License-GPL--2.0--only-111111?style=flat-square" />

<br/>

<img alt="Device" src="https://img.shields.io/badge/Device-OnePlus%2013%20CN%20(PJZ110%20%C2%B7%20sun)-111111?style=flat-square" />
<img alt="ROM" src="https://img.shields.io/badge/ROM-ColorOS%2017%20CN%20(Android%2017)-111111?style=flat-square" />
<img alt="Kernel" src="https://img.shields.io/badge/Kernel-6.6.118%20(GKI%202.0)-111111?style=flat-square" />
<img alt="SUSFS" src="https://img.shields.io/badge/SUSFS-v2.3.0%20(CCTV18)-111111?style=flat-square" />

</div>

---

## Overview

A daily‑driver focused **Linux 6.6 GKI 2.0** kernel for the **OnePlus 13 CN**
(`PJZ110` / `sun` / `SM8750`), built entirely from GitHub Actions and targeting
**ColorOS 17 CN (Android 17)**. The goal is a **stock‑like, stable, battery‑friendly
baseline** with modern root + SUSFS hiding — not a maxed‑out benchmark build.

Two root solutions are offered as separate build **lanes**, both sharing the same
CCTV18 OP13 source, toolchain and SUSFS tree:

| Lane | Workflow | Root solution | Manager APK | Pick it if… |
|---|---|---|---|---|
| **BakaSU** (Recommended) | `Build_ReSukiSU.yml` | [BakaSU](https://github.com/Baka-SU/BakaSU) (formerly ReSukiSU) | latest BakaSU manager | you want the daily driver — the most tested lane |
| **SukiSU Ultra** | `Build SukiSU_Ultra.yml` | [SukiSU‑Ultra](https://github.com/SukiSU-Ultra/SukiSU-Ultra) (`builtin` branch) | **v4.2.0 only** (`SukiSU_v4.2.0_40900`) | you want SukiSU Ultra with KPM support |

> [!IMPORTANT]
> **SukiSU lane: do not install manager v4.2.1.** v4.2.1 requires kernel UAPI 5,
> while SukiSU's `builtin` branch (the only branch with SUSFS support) still
> reports UAPI 2. With v4.2.1 the manager shows root as unavailable and App
> Profile writes fail. Use **`SukiSU_v4.2.0_40900_releases.apk`**.

> **About "android15" in the version string.** `uname -r` contains
> `android15-8` on **stock ColorOS 17 too** — it names the GKI kernel branch
> (`android15-6.6`), not the Android version. OnePlus ships the 6.6 GKI kernel on
> Android 17, so this is correct and must not be changed.

> **ReSukiSU is now BakaSU.** The project was renamed upstream; the workflow file
> keeps its old name (`Build_ReSukiSU.yml`) so existing Actions links and history
> keep working.

> **KernelSU‑Next lane is DEPRECATED** (archived at
> [`docs/deprecated/Build_KSUN.yml.deprecated`](./docs/deprecated/Build_KSUN.yml.deprecated)).
> See [`docs/deprecated/WHY_KSUN_DEPRECATED.md`](./docs/deprecated/WHY_KSUN_DEPRECATED.md).

> **Current release line: SukiSU Ultra `v114` · BakaSU `v111`** — ColorOS 17
> stock uname, ADIOS + Re:Kernel + Baseband‑Guard actually enabled, two
> upstream security fixes. See
> [`docs/RELEASE_v114_v111.md`](./docs/RELEASE_v114_v111.md).

---

## Build matrix

Both lanes are **manually triggered** (`workflow_dispatch`) and every upstream is
**pinned to a commit**, because unpinned upstreams have broken this project
several times.

| Component | Source | Pin |
|---|---|---|
| Kernel | `cctv18/android_kernel_common_oneplus_sm8750` @ `oneplus/sm8750_b_16.0.0_oneplus_13_6.6.118` | `2a4726b` (6.6.118) |
| SUSFS — BakaSU lane | `cctv18/susfs4oki` (`oki-android15-6.6`) | `3f6aae5` (v2.3.0) |
| SUSFS — SukiSU lane | `cctv18/susfs4oki` (`oki-android15-6.6`) | `2919a9a` (v2.3.0) |
| BakaSU driver | `Baka-SU/BakaSU` `main` | `d7260ca` |
| SukiSU driver | `SukiSU-Ultra/SukiSU-Ultra` `builtin` | `2d1de62` |
| Build assets | `cctv18/oppo_oplus_realme_sm8750` | `21db9e7` |
| Packaging | [osm0sis/AnyKernel3](https://github.com/osm0sis/AnyKernel3) | `020dfec` |
| Toolchain | CCTV18 prebuilt LLVM/Clang 18 (`r510928`) | release tag |

> **Why the two lanes use different SUSFS commits.** SukiSU builtin's SELinux
> hiding links against two helpers that SUSFS removed in `3f6aae5`, so the SukiSU
> lane stays on `2919a9a` (same SUSFS v2.3.0). BakaSU ships its own SELinux hiding
> and uses the newer `3f6aae5`. **Driver and SUSFS must be the same generation** —
> both workflows have a pairing guard that fails the build on a mismatch.

### Key inputs (set them when you press *Run workflow*)

| Input | What it does | Default |
|---|---|---|
| `profile` | `stock_daily` / `stock_plus` / `minimal_safe` / `debug_only` | `stock_daily` |
| `sukisu_ref` / `resukisu_ref` | Root driver commit (keep paired with `susfs_ref`) | pinned commit |
| `susfs_ref` | SUSFS commit | pinned commit |
| `SUSFS` | Enable CCTV18 SUSFS | On |
| `susfs_patch_policy` | `audited_cctv18` / `strict` / `native_cctv18` | `audited_cctv18` |
| `hook_mode` | Hook target (inline SUSFS vs. auto/test modes) | `inline_susfs` |
| `kpm_enable` | Kernel‑side KPM (SukiSU only; BakaSU has none) | SukiSU: on · BakaSU: off |
| `kernel_suffix` | Stock‑mimic `LOCALVERSION` (controls `uname -r`) | ColorOS 17 CN stock value |
| `kernel_name` | Display banner shown by the flasher | lane name |
| `optimise` | `O2` (stable) or `O3` (test‑only) | `O2` |
| `zram_module` / `zram_comp` | ZRAM + LZ4/LZ4HC/ZSTD in config / preferred compressor | On / `lz4` |
| `lz4_zram_patch` | Extra LZ4 ZRAM patch (touches kernel headers → KMI risk) | Off |
| `bbr` | TCP BBR (`On` = available, `Default` = default congestion control) | On |
| `proxy` | Netfilter extras (HL target/match, IP_SET) | On |
| `adios` / `rekernel` / `bbg` | ADIOS I/O scheduler / Re:Kernel / Baseband‑Guard | On |
| `fengchi` | FengChi/HMBIRD scheduler (experimental) | Off |
| `BUILD_USER` / `BUILD_HOST` | `/proc/version` identity | `kleaf` / `build-host` (stock GKI) |
| `clean_ccache` | Wipe ccache before building | false |

> **Moving ROMs?** `kernel_suffix` defaults to the ColorOS 17 CN stock value
> `android15-8-g9bc34d5b0c79-abogki537459655-4k`. For ColorOS 16 use
> `android15-8-g93e223c276e7-abogki500782043-4k`. The kernel source is the same
> 6.6.118 for both.

### Outputs

Each run uploads one artifact containing:

- `Image_OP13_…` — raw kernel image (+ `.sha256`)
- `AK3_OP13_…_FLASH_THIS.zip` — AnyKernel3 flashable ZIP (+ `.sha256`)
- `_ox_debug/` — logs, final `.config`, patch audit and check results:
  - `pairing.txt` — must say `pairing: OK`
  - `susfs-config-audit.txt` — every requested SUSFS option is `=y`
  - `cve-status.txt`, `sec-posix-timers.txt` — security fixes applied

---

## Features

- **GKI 2.0** packaging as an AnyKernel3 flashable ZIP
- **Root:** BakaSU **or** SukiSU Ultra (one per lane)
- **SUSFS v2.3.0** (CCTV18 `susfs4oki`) with inline hook — SUS path / mount /
  kstat / map, `uname` spoof, cmdline/bootconfig spoof, open‑redirect, KSU/SUSFS
  symbol hiding (SUSFS logging is off to save battery)
- **SELinux context hiding** — BakaSU's own implementation, or SukiSU builtin's
  with the matching SUSFS pair
- **Stock‑mimic identity** — `uname -r` matches ColorOS 17 CN exactly (no trailing
  `+`), and `/proc/version` reports the stock `kleaf@build-host`
- **ADIOS** I/O scheduler (set as default), **Re:Kernel**, **Baseband‑Guard** LSM
- **ZRAM** with LZ4 / LZ4HC / ZSTD, **TCP BBR**, **NTSYNC**, netfilter extras
- **Security fixes** on top of CCTV18's source: CVE‑2026‑43499 (rtmutex) and the
  6.6‑stable posix‑cpu‑timers use‑after‑free fix
- **KPM** support on the SukiSU lane (kernel support only — no modules bundled)

**Companion module:** **X1 Kernel Manager** (`ox_op13_kernel_manager`) — WebUI
for profiles, ZRAM, charging and live stats, plus the SUSFS privacy layer (path /
map / uname / mount hiding) and an attestation preflight. Runtime tuning lives in
the module rather than the kernel, to stay within GKI 2.0 KMI limits.

---

## Safety first

> ⚠️ Flashing kernels can cause **bootloops**, **soft‑bricks**, **data loss** and
> **instability**. You are responsible for what you flash. If you can't recover
> from a bootloop, **don't flash**.

**Back up before flashing.** Back up `boot` and `init_boot`
(and `vbmeta` if your setup uses it).

**If you bootloop:**
1. Reboot to recovery / fastboot.
2. Restore your `boot` / `init_boot` backup (or flash the stock `boot.img` for
   your exact ColorOS build).
3. Reboot.

---

## Install

1. Download the correct `AK3_OP13_…_FLASH_THIS.zip` from **Releases** (or the
   **Actions** run artifact).
2. Flash it with a kernel flasher or your root manager's AnyKernel3 flasher.
3. Reboot.
4. Install the matching manager APK — **BakaSU:** latest BakaSU manager ·
   **SukiSU:** **v4.2.0** (not v4.2.1).
5. Optional: install **X1 Kernel Manager**. On BakaSU, mount hiding needs the
   `ksu_susfs` binary (from the susfs4ksu module); SukiSU v4.2.0's `ksud` has it
   built in.

> Switching lanes (e.g. SukiSU → BakaSU)? Reinstall your SUSFS/manager modules
> afterwards to clear stale state.

---

## Verify after flashing

```sh
# Stock-mimic uname — should end in "-4k" with no trailing "+"
uname -r
# expected: 6.6.118-android15-8-g9bc34d5b0c79-abogki537459655-4k

# SUSFS kernel options
su -c 'zcat /proc/config.gz | grep -E "^CONFIG_KSU_SUSFS(_SUS_PATH|_SUS_MOUNT|_SUS_KSTAT|_SUS_MAP|_SPOOF_UNAME)?="'

# ADIOS scheduler, Re:Kernel, Baseband-Guard
su -c 'zcat /proc/config.gz | grep -E "^CONFIG_(MQ_IOSCHED_ADIOS|REKERNEL|BBG)="'

# ZRAM + active compressor
su -c 'cat /sys/block/zram0/comp_algorithm 2>/dev/null; cat /proc/swaps'

# SukiSU lane: manager crowned early in boot
su -c 'dmesg | grep -E "scanning manager|Crowning manager"'
```

---

## Troubleshooting

- **`su` fails in Termux/adb with `cannot execute: required file not found`, but
  apps still get root** — driver and SUSFS are from different generations. Use
  the pinned defaults; check `_ox_debug/pairing.txt`.
- **SukiSU: root unavailable / App Profile writes fail** — you installed manager
  v4.2.1. Install **v4.2.0**.
- **SukiSU: "Failed to grant Root!" until the manager is restarted** — fixed in
  v114 (early manager scan at post‑fs‑data). Update the kernel.
- **SUSFS module "operation not supported" / `0x555e1`** — reinstall the SUSFS
  module after flashing; if you had a different one before, uninstall it, reboot,
  then install the correct one.
- **No `zram.ko`** — ZRAM is built in; check `/proc/swaps` and
  `/sys/block/zram0/comp_algorithm`.
- **Bootloop** — restore `boot` / `init_boot`, return to the `stock_daily`
  profile and re‑introduce options one at a time.
- **TEE / Soter attestation flagged by a detector** — expected on an unlocked
  bootloader. The secure world learns the boot state from the boot chain; no
  kernel or module can change that.

---

## Build it yourself

Open **Actions → pick a lane → Run workflow**, choose your inputs, and download
the artifact when it finishes. Start from `stock_daily` + `O2` + inline SUSFS with
the pinned refs, then experiment from a fork. If you change a root ref, change
`susfs_ref` with it — the pairing guard will stop a mismatched build.

### Maintenance utilities
- **Clean Caches** (`Clean Caches.yml`) — purge `ccache-*` Actions caches.
- **Cleanup CCache** (`clean-up.yml`) — bulk cache/run cleanup with filters.
- **Lint Workflows** (`lint.yml`) — actionlint + yamllint on every workflow change.

### Portable composite action (advanced)
`action.yml` is a separate, **device‑agnostic** builder that syncs sources with
Google's `repo` tool (`manifest.xml`), pulls AnyKernel3/`kernel_patches` from
TheWildJames + SUSFS from `simonpunk/susfs4ksu`, and applies a broad OnePlus
patch set. It is intended for forks/other devices and is **not** what the OP13
release lanes above use. See `docs/REVIEW.md`.

---

## Credits

[@cctv18](https://github.com/cctv18) ·
[BakaSU](https://github.com/Baka-SU) ·
[SukiSU‑Ultra](https://github.com/SukiSU-Ultra) ·
[@simonpunk (SUSFS)](https://gitlab.com/simonpunk/susfs4ksu) ·
[@osm0sis (AnyKernel3)](https://github.com/osm0sis) ·
[@mrcxlinux](https://github.com/mrcxlinux) ·
[@WildKernels / @TheWildJames](https://github.com/WildKernels) ·
[KernelSU‑Next](https://github.com/KernelSU-Next) (former lane)

---

## License

Distributed under **GPL‑2.0‑only** (see [`LICENSE`](./LICENSE)), matching the
upstream Linux kernel and SUSFS sources this project builds on. Build glue and
workflows are covered by the same license. Bundled third‑party components
(AnyKernel3, root solutions, CCTV18 patches) remain under their own upstream
licenses — follow those where applicable.
