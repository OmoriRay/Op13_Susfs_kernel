#!/usr/bin/env bash
set -euo pipefail
variant="$1"
stage="${2:-all}"
case "$stage" in all|prepare|precheck|compile|package) ;; *) exit 2 ;; esac
root="$(pwd)"
profile_options="$(python3 - "$variant" <<'PY'
import json,sys
from pathlib import Path
profile=json.loads(Path('scripts/extreme/profiles.json').read_text())[sys.argv[1]]
assert profile['lto'] in ['thin','full'] and profile['hz'] in [250,1000]
assert profile['adios'] in ['3.1.6','3.3.0'] and profile['mtune'] in [None,'oryon-1']
print(int(profile['adios']=='3.3.0'),profile['mtune'] or 'none')
PY
)"
read -r profile_adios33 profile_mtune <<< "$profile_options"
report="$root/reports/$variant"
mkdir -p "$report" toolchain
export PATH="$root/toolchain/bin:$PATH"
export LD_LIBRARY_PATH="$root/toolchain/lib:${LD_LIBRARY_PATH:-}"
export KBUILD_BUILD_USER=OmoriRay KBUILD_BUILD_HOST=GitHubActions
export KBUILD_BUILD_TIMESTAMP="$(git show -s --format=%cD HEAD)"
export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
if [[ "$stage" == prepare || "$stage" == all ]]; then
python3 - "$variant" <<'PY'
import json,sys
from pathlib import Path
import subprocess
patches=['0004-counted-by-genksyms-compat.patch']
profile=json.loads(Path('scripts/extreme/profiles.json').read_text())[sys.argv[1]]
if profile['adios']=='3.3.0':patches.append('0100-adios-3.3.0-backport.patch')
for name in patches:
    patch=Path('patches/extreme',name).resolve()
    for options in [['--check'],[]]:
        subprocess.run(['git','apply',*options,'--directory=kernel_workspace/common','--whitespace=error-all',str(patch)],check=True)
if profile['adios']=='3.3.0':assert '#define ADIOS_VERSION "3.3.0"' in Path('kernel_workspace/common/block/adios.c').read_text()
PY
python3 - <<'PY'
import json,subprocess,hashlib
from pathlib import Path
x=json.loads(Path('scripts/extreme/sources.json').read_text())['llvm'];p=Path('toolchain/llvm.tar.zst')
if not p.is_file() or hashlib.file_digest(p.open('rb'),'sha256').hexdigest()!=x['sha256']:
    subprocess.run(['curl','--fail','--location','--retry','3','--silent','--show-error',x['url'],'-o',str(p)],check=True)
assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==x['sha256']
subprocess.run(['tar','--use-compress-program=zstd -d --long=31','-xf',str(p),'--strip-components=1','-C','toolchain'],check=True)
p.unlink()
PY
clang --version | tee "$report/clang-version.txt"
ld.lld --version | tee "$report/lld-version.txt"
clang --version | grep -F '23.1.5'
python3 scripts/extreme/configure.py "$variant"
fi
out="$root/kernel_workspace/out-$variant"
args=(-C "$root/kernel_workspace/common" "O=$out" ARCH=arm64 LLVM=1 LLVM_IAS=1)
if [[ "$profile_mtune" != none ]]; then args+=("KCFLAGS=-mtune=$profile_mtune"); fi
if [[ "$stage" == precheck || "$stage" == all ]]; then
make "${args[@]}" -j2 V=1 KBUILD_SYMTYPES=1 fs/proc/task_mmu.o fs/susfs.o mm/huge_memory.o block/adios.o drivers/interconnect/core.o 2>&1 | tee "$report/precheck.log"
if [[ "$variant" == lab-thin-zram-ab ]]; then
    make "${args[@]}" -j2 V=1 lib/op13_lz4/ drivers/block/zram/zcomp.o 2>&1 | tee "$report/zram-precheck.log"
    cp "$root/kernel_workspace/common/lib/op13_lz4/source-manifest.json" "$report/lz4-source-manifest.json"
    llvm-nm --defined-only "$out/lib/op13_lz4/built-in.a" > "$report/lz4-private-symbols.txt"
    if grep -E '[[:space:]][TWDB][[:space:]]LZ4_' "$report/lz4-private-symbols.txt"; then
        echo 'Unnamespaced upstream LZ4 symbol in private backend' >&2; exit 1
    fi
fi
python3 - "$out" "$report" <<'PY'
import sys,json,re,shutil
from pathlib import Path
out=Path(sys.argv[1]);report=Path(sys.argv[2]);records=[]
profile=json.loads((report/'profile-spec.json').read_text())
for name in ['fs/proc/.task_mmu.o.cmd','fs/.susfs.o.cmd','mm/.huge_memory.o.cmd','block/.adios.o.cmd']:
    text=(out/name).read_text();assert ' -O3 ' in text,name
    assert '-fsanitize=kcfi' in text or '-fsanitize=cfi' in text,name
    lto_ok=('-flto=thin' in text) if profile['lto']=='thin' else ((' -flto ' in text or '-flto=full' in text) and '-flto=thin' not in text)
    tune_ok=('-mtune=oryon-1' in text)==(profile['mtune']=='oryon-1')
    assert lto_ok and tune_ok,name
    records.append({'file':name,'O3':True,'CFI':True,'LTO':profile['lto'],'mtune':profile['mtune'],'LTO_checked':True,'mtune_checked':True})
(report/'compiler-command-checks.json').write_text(json.dumps(records,indent=2))
text=(out/'drivers/interconnect/.core.o.cmd').read_text()
actual={k:int(v,16) for k,v in re.findall(r'#SYMVER\s+(\w+)\s+(0x[0-9a-fA-F]+)',text)}
samples=json.loads(Path('scripts/extreme/vendor-imports.json').read_text())
names=['icc_set_bw','icc_set_tag','of_icc_get','icc_put']
expected={v['symbol']:int(v['crc'],16) for m in samples['modules'] for v in m['imports'] if v['symbol'] in names}
checks=[{'symbol':k,'expected':hex(expected[k]),'actual':hex(actual[k]) if k in actual else None} for k in names]
print('Interconnect CRC precheck:',json.dumps(checks))
(report/'interconnect-crc-precheck.json').write_text(json.dumps(checks,indent=2))
symtypes=out/'drivers/interconnect/core.symtypes'
if symtypes.exists():shutil.copyfile(symtypes,report/'interconnect-core.symtypes')
assert all(actual.get(k)==expected[k] for k in names),'Interconnect CRC precheck failed; no full build started'
PY
fi
if [[ "$stage" == compile || "$stage" == all ]]; then
jobs="$(nproc)"
if [[ "$jobs" -gt 4 ]]; then jobs=4; fi
make "${args[@]}" -j"$jobs" Image modules 2>&1 | tee "$report/build.log"
cp "$out/Module.symvers" "$report/Module.symvers"
cp "$out/vmlinux.symvers" "$report/vmlinux.symvers"
python3 scripts/extreme/verify_abi.py "$variant"
llvm-readelf -h "$out/vmlinux" > "$report/vmlinux-elf-header.txt"
llvm-nm -n "$out/vmlinux" | grep -E 'ksu_handle_susfs_cmd|susfs_set_priority_uid_filter|smap_gather_stats|hmbird|slim_walt' > "$report/integrated-symbols.txt"
cp "$out/include/generated/utsrelease.h" "$report/utsrelease.h"
mkdir -p artifacts
zstd -T2 -5 "$out/vmlinux" -o "artifacts/vmlinux-$variant.zst"
fi
if [[ "$stage" == package || "$stage" == all ]]; then
python3 scripts/extreme/package.py "$variant"
fi
