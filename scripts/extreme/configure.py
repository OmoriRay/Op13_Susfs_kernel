#!/usr/bin/env python3
import argparse,json,os,subprocess
from pathlib import Path

profiles=json.loads(Path(__file__).with_name('profiles.json').read_text())
p=argparse.ArgumentParser();p.add_argument('variant',choices=profiles);a=p.parse_args()
profile=profiles[a.variant]
assert profile['lto'] in ['thin','full'] and profile['hz'] in [250,1000]
assert profile['adios'] in ['3.1.6','3.3.0'] and profile['mtune'] in [None,'oryon-1']
root=Path(__file__).resolve().parents[2];common=root/'kernel_workspace/common'
out=root/'kernel_workspace'/('out-'+a.variant);report=root/'reports'/a.variant;report.mkdir(parents=True,exist_ok=True)
args=['make','-C',str(common),'O='+str(out),'ARCH=arm64','LLVM=1','LLVM_IAS=1']
def run(*cmd):subprocess.run(cmd,check=True)
run(*args,'gki_defconfig')
cfg=out/'.config';config=common/'scripts/config'
def setval(option,value):
    mode='-e' if value is True else '-d' if value is False else '--set-val'
    cmd=[str(config),'--file',str(cfg),mode,option]
    if value is not True and value is not False:cmd.append(str(value))
    run(*cmd)
def string(option,value):run(str(config),'--file',str(cfg),'--set-str',option,value)
enabled=['KSU','KSU_SUSFS','KSU_MULTI_MANAGER_SUPPORT','KSU_SUSFS_PRIORITY_UID_FILTER',
 'KSU_SUSFS_SUS_PATH','KSU_SUSFS_SUS_MOUNT','KSU_SUSFS_SUS_KSTAT','KSU_SUSFS_SUS_MAP',
 'KSU_SUSFS_SPOOF_UNAME','KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG','KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS','KSU_SUSFS_OPEN_REDIRECT',
 'CC_OPTIMIZE_FOR_PERFORMANCE_O3','CFI_CLANG','MODVERSIONS','IKCONFIG','IKCONFIG_PROC',
 'ARM64_4K_PAGES','PREEMPT','HMBIRD_SCHED','UCLAMP_TASK','UCLAMP_TASK_GROUP',
 'TRANSPARENT_HUGEPAGE','TRANSPARENT_HUGEPAGE_MADVISE','OP13_MTHP_64K_DEFAULT','LRU_GEN','LRU_GEN_ENABLED',
 'ZSMALLOC','ZRAM','ZRAM_DEF_COMP_LZ4','ZRAM_MULTI_COMP','ZRAM_WRITEBACK','ZRAM_TRACK_ENTRY_ACTIME','ZRAM_MEMORY_TRACKING',
 'CRYPTO_LZ4','CRYPTO_LZ4HC','CRYPTO_ZSTD','LZ4_COMPRESS','LZ4_DECOMPRESS','ZSTD_COMPRESS','ZSTD_DECOMPRESS',
 'MQ_IOSCHED_ADIOS','MQ_IOSCHED_DEFAULT_ADIOS','MQ_IOSCHED_DEADLINE','MQ_IOSCHED_KYBER','IOSCHED_BFQ',
 'REKERNEL','TCP_CONG_BBR','NET_SCH_FQ','NET_SCH_FQ_CODEL','TMPFS_XATTR','TMPFS_POSIX_ACL']
disabled=['KSU_TRACEPOINT_HOOK','KSU_MANUAL_HOOK','KSU_DEBUG','KSU_SUSFS_ENABLE_LOG','CFI_PERMISSIVE',
 'CC_OPTIMIZE_FOR_PERFORMANCE','CC_OPTIMIZE_FOR_SIZE','LOCALVERSION_AUTO','TRANSPARENT_HUGEPAGE_ALWAYS',
 'ZRAM_DEF_COMP_LZORLE','ZRAM_DEF_COMP_ZSTD','ZRAM_DEF_COMP_LZO','ZRAM_DEF_COMP_LZ4HC','AUTOFDO_CLANG']
for flag in enabled:setval(flag,True)
for flag in disabled:setval(flag,False)
full=profile['lto']=='full'
setval('LTO_CLANG_THIN',not full);setval('LTO_CLANG_FULL',full);setval('LTO_NONE',False)
setval('HZ_250',profile['hz']==250);setval('HZ_1000',profile['hz']==1000)
setval('ZSMALLOC_CHAIN_SIZE',16)
suffix='-op13-v2'+('-'+a.variant if a.variant.startswith('lab-thin-') else '')
string('KSU_FULL_NAME_FORMAT','%TAG_NAME%-%COMMIT_SHA%'+suffix)
string('LOCALVERSION','-android15-8-g9bc34d5b0c79-abogki537459655-4k')
run(*args,'olddefconfig')
text=cfg.read_text();values={}
for line in text.splitlines():
    if line.startswith('CONFIG_') and '=' in line:
        k,v=line.split('=',1);values[k[7:]]=v
for flag in enabled:assert values.get(flag)=='y',(flag,values.get(flag))
for flag in disabled:assert values.get(flag) not in ['y','m'],flag
assert values.get('LTO_CLANG_FULL' if full else 'LTO_CLANG_THIN')=='y'
assert values.get('HZ')==str(profile['hz'])
assert values.get('ZSMALLOC_CHAIN_SIZE')=='16'
assert values.get('ZRAM_DEF_COMP')=='"lz4"'
assert values.get('ARM64_PAGE_SHIFT')=='12'
(report/'final.config').write_text(text)
manifest={'variant':a.variant,'actual_kernel':'6.6.118','compiler_target':'LLVM 23.1.5','optimization':'O3',
 'lto':'full' if full else 'thin','hz':int(values['HZ']),'mthp_64k_default':True,'zsmalloc_chain_size':16,
 'adios':'3.3.0 backport' if profile['adios']=='3.3.0' else '3.1.6','mtune':'oryon-1 experimental' if profile['mtune'] else 'unchanged',
 'cfi':'enforcing','vendor_ABI_verified':False,'boot_tested':False,'performance_tested':False}
(report/'profile.json').write_text(json.dumps(manifest,indent=2))
(report/'profile-spec.json').write_text(json.dumps(profile,indent=2))
print(json.dumps(manifest))
