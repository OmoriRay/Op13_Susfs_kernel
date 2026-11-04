#!/usr/bin/env bash
set -euo pipefail
variant="$1"
root="$(pwd)"
report="$root/reports/$variant"
mkdir -p "$report" toolchain
python3 - "$variant" <<'PY'
import json,sys
from pathlib import Path
import subprocess
if sys.argv[1]=='lab-max':
    patch=Path('patches/extreme/0100-adios-3.3.0-backport.patch').resolve()
    for options in [['--check'],[]]:
        subprocess.run(['git','apply',*options,'--directory=kernel_workspace/common','--whitespace=error-all',str(patch)],check=True)
    assert '#define ADIOS_VERSION "3.3.0"' in Path('kernel_workspace/common/block/adios.c').read_text()
PY
python3 - <<'PY'
import json,subprocess,hashlib
from pathlib import Path
x=json.loads(Path('scripts/extreme/sources.json').read_text())['llvm'];p=Path('toolchain/llvm.tar.zst')
subprocess.run(['curl','--fail','--location','--retry','3','--silent','--show-error',x['url'],'-o',str(p)],check=True)
assert hashlib.file_digest(p.open('rb'),'sha256').hexdigest()==x['sha256']
subprocess.run(['tar','--use-compress-program=zstd -d --long=31','-xf',str(p),'--strip-components=1','-C','toolchain'],check=True)
p.unlink()
PY
export PATH="$root/toolchain/bin:$PATH"
export LD_LIBRARY_PATH="$root/toolchain/lib:${LD_LIBRARY_PATH:-}"
clang --version | tee "$report/clang-version.txt"
ld.lld --version | tee "$report/lld-version.txt"
clang --version | grep -F '23.1.5'
export KBUILD_BUILD_USER=OmoriRay KBUILD_BUILD_HOST=GitHubActions
export KBUILD_BUILD_TIMESTAMP="$(git show -s --format=%cD HEAD)"
export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
python3 scripts/extreme/configure.py "$variant"
out="$root/kernel_workspace/out-$variant"
args=(-C "$root/kernel_workspace/common" "O=$out" ARCH=arm64 LLVM=1 LLVM_IAS=1)
if [[ "$variant" == lab-max ]]; then args+=(KCFLAGS=-mtune=oryon-1); fi
make "${args[@]}" -j2 V=1 fs/proc/task_mmu.o fs/susfs.o mm/huge_memory.o block/adios.o 2>&1 | tee "$report/precheck.log"
python3 - "$out" "$report" <<'PY'
import sys,json
from pathlib import Path
out=Path(sys.argv[1]);report=Path(sys.argv[2]);records=[]
for name in ['fs/proc/.task_mmu.o.cmd','fs/.susfs.o.cmd','mm/.huge_memory.o.cmd','block/.adios.o.cmd']:
    text=(out/name).read_text();assert ' -O3 ' in text,name
    assert '-fsanitize=kcfi' in text or '-fsanitize=cfi' in text,name
    records.append({'file':name,'O3':True,'CFI':True})
(report/'compiler-command-checks.json').write_text(json.dumps(records,indent=2))
PY
jobs="$(nproc)"
if [[ "$jobs" -gt 4 ]]; then jobs=4; fi
make "${args[@]}" -j"$jobs" Image modules 2>&1 | tee "$report/build.log"
cp "$out/Module.symvers" "$report/Module.symvers"
cp "$out/vmlinux.symvers" "$report/vmlinux.symvers"
llvm-readelf -h "$out/vmlinux" > "$report/vmlinux-elf-header.txt"
llvm-nm -n "$out/vmlinux" | grep -E 'ksu_handle_susfs_cmd|susfs_set_priority_uid_filter|smap_gather_stats|hmbird|slim_walt' > "$report/integrated-symbols.txt"
cp "$out/include/generated/utsrelease.h" "$report/utsrelease.h"
mkdir -p artifacts
zstd -T2 -5 "$out/vmlinux" -o "artifacts/vmlinux-$variant.zst"
python3 scripts/extreme/package.py "$variant"
