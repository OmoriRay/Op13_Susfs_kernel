# OP13 Memory Companion v1.0.1（实验版）

面向 PJZ110 / OP5D0DL1、ColorOS 17.0.0.103、已审查的 Android 17 fingerprint。

这版采用 Pandora 类似的交付方式：AK3 包含已编译的 `lab-thin-max` Image，以及刷完 boot 后通过 BakaSU 安装的独立策略模块。底座是先前成功启动的 6.6.118 / LLVM23.1.5 / O3 / ThinLTO / ADIOS3.3.0 / oryon-1 / 64K mTHP；**这次没有重新编译或修改 Image**。不能据此声称内核版本更新、私有算法移植或性能提升。

## 策略

| 档位 | 主算法 | 逻辑容量 | swappiness | page-cluster | watermark_scale_factor |
|---|---|---|---|---|---|
| pandora_like（默认） | LZ4 | 2×MemTotal | 100 | 0 | 200 |
| density（实验） | ZSTD | 2×MemTotal | 100 | 0 | 200 |
| game（对照） | LZ4 | 1×MemTotal | 60 | 0 | 150 |

逻辑容量按 4K 对齐，不会预占同等物理内存。独立 `mem_limit` 为0；保留内核与 Android 的内存保护。存在 MGLRU TTL 节点时设置1000ms。未改 LMKD、CPU/GPU、温控、A-SOUL、Scene EP、THP 或降压。没有 Pandora 的 `zstdp/lz4p/mm_vhs` 源码，未把这些私有实现伪装成标准 LZ4/ZSTD。

内核已有多压缩与重压缩能力。LZ4 档在初始化之前配置 ZSTD 二级算法（接口存在时）；v1没有自动重压缩守护进程，也不声称冷页已被自动重压缩。未配置 UFS 写回；检测到已有 backing_dev 时退出接管。

## 启动与冲突处理

独立模块在 BakaSU 管理器内安装；AK3 整合包刷完 boot 后调用 `/data/adb/ksud module install`，不能用 Fastboot 直接刷 ZIP。整合安装不是原子事务：若模块安装失败，会明确提示 boot 写入已完成及模块失败，不能当作两者均成功。

安装器只支持已审查的 X1 2.13.0，在它的 `zram_apply` 和 `ram_expand_apply` 函数开头插入有标记的接管判断，备份原文件到 `/data/adb/op13_memory/`。X1 的隐藏、完整性、充电及其他功能保持原代码。未知版本拒绝安装，不能靠“关闭 ZRAM”选项代替交接。已启用的 Pandora 配套模块会阻止启动接管。

模块仅在一次启动中尝试一次初始化。对已启用交换空间，仅在开机180秒内、使用量不超过64MiB、MemAvailable至少2GiB时允许一次切换；超限则保留现有交换区并报告 adopted-existing，不声称目标容量/算法已生效。所有交换命令明确调用系统 Toybox，避开 BusyBox standalone 对 `swapon -p` 的不兼容。

启动按顺序检查退出码、`/proc/swaps`、`SwapTotal`、实际算法和容量。失败尝试恢复之前的算法/容量并启用交换，原容量小于1GiB时视为异常小容量，使用75% MemTotal的基线容量。不会反复重试或通过删块设备节点、遮罩挂载强迫其他管理器失效。系统初始化并发仍需实机验证，不能仅靠脚本模拟宣布兼容。

## v1.0.1 修复与升级

v1.0.0存在已经在PJZ110实机确认的Android mksh 32位算术缺陷。目标容量与备用容量计算会溢出，`[ 4294967296 -gt 0 ]`等字节数比较也会溢出；在MemTotal=23613496KiB时，目标计算得到-888832，备用计算得到10399744字节。观察到模块进入恢复流程，最终仅启用10152KiB swap，不能将这次情况解释为旧X1故障。

v1.0.1将所有字节容量运算和大整数比较移至awk，加入最小容量检查，记录请求值、失败节点/值/返回码，并保存service.log。25项宿主测试在普通sh及mksh下执行；实际手机中只读验证容量/比较函数，不等于已验证修正版完整初始化。Android mksh使用32位算术是明确的实现行为，见[官方源码中的FAQ](https://android.googlesource.com/platform/external/mksh/+/13fd1d1f9cf2fe029e2258c7528d2e985c6fd314/src/mksh.faq)。

已经安装v1.0.0时，推荐在BakaSU模块页直接安装独立v1.0.1 ZIP覆盖同一module ID，再重启；不必先卸载，也不需要重复写入相同内核。X1交接插入是幂等的，已有两处标记会保留。也提供同版本AK3整合包，但它的Image仍与原lab-thin-max相同。默认策略不变。

## 状态、切档与回退

管理器的模块操作按钮显示状态；也可执行：

```sh
su -c '/system/bin/sh /data/adb/modules/op13_memory/memory.sh status'
su -c '/system/bin/sh /data/adb/modules/op13_memory/memory.sh profile density'
```

允许的档名为 `pandora_like`、`density`、`game`。保存后重启才应用；不在运行游戏时重设 ZRAM。日志和实际生效值在 `/data/adb/op13_memory/memory.log`、`status.txt`。

停用模块后重启，X1 的接管判断立即让回控制权。卸载仅移除本模块插入的判断，不用旧备份覆盖整个 X1 文件，避免抹掉用户后续更新。**原 X1 的 BusyBox swapon兼容性缺陷仍存在，回退到原 X1 不等于修复原缺陷**；若它再次出现 SwapTotal=0，需要修复其工具调用或恢复系统初始化，不能靠重复刷内核解决。卸载时不关闭当前正在使用的交换区。

若出现模块引起的启动问题，使用 BakaSU 的模块救援方式或可用 root shell 创建 `/data/adb/modules/op13_memory/disable` 后重启。若系统已不能获得 root，需要先恢复已备份的可启动 boot，不能假定 Fastboot 能修改 `/data`。已验证 v111 基线完整 boot 的 SHA-256为 `74685314b6eb73ad23862fdd47c69afa5f0686d424473a6201d26e7a9be1822a`；只供原先同一 ROM/槽位条件，刷写前重新核对。AK3不随包夹带个人 boot 备份。

## 验收边界

旧底座的正式启动原始日志去色后有9条 CPU WARNING，涉及 proc 注册、页分配、IRQ 和厂商热线程统计；未证明由 ZRAM 引起，也没有在本次打包中修复。已有启动记录不能替代新模块与新整合包的实机验收。本版仅允许宣称通过源码/宿主回归/包内容检查。

首次实机验收应保存 `/proc/swaps`、`/proc/meminfo`、ZRAM `mm_stat/io_stat`、模块日志和去色 dmesg，确认 SwapTotal>0、zram0交换条目存在且参数与 requested/actual 状态一致。之后固定 Scene EP、A-SOUL、游戏场景和环境温度，对比三档的帧时间P95/P99、应用重载、PSI、swapin/out、压缩内存、功耗与温度；不以容量更大或压缩率更高替代游戏性能结果。

## 依据

- [Linux ZRAM 文档](https://docs.kernel.org/admin-guide/blockdev/zram.html)
- [Linux VM 参数说明](https://docs.kernel.org/admin-guide/sysctl/vm.html)
- [MGLRU TTL](https://docs.kernel.org/admin-guide/mm/multigen_lru.html)
- [KernelSU 模块与 BusyBox standalone](https://kernelsu.org/guide/module.html)
- [精确底座 ZRAM 驱动](https://github.com/cctv18/android_kernel_common_oneplus_sm8750/blob/2a4726b11594dd57d0779d2685fad5c81e5ed553/drivers/block/zram/zram_drv.c)
- [原始内核构建41965278315](https://github.com/OmoriRay/Op13_Susfs_kernel/actions/runs/41965278315)
