#!/usr/bin/env python3
"""Pair newly compiled AB Image with its module; never accept the old Image."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import zlib

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('memory_package',ROOT/'scripts/memory/package.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
sha=lambda blob:hashlib.sha256(blob).hexdigest()
variant='lab-thin-zram-ab'
out=ROOT/'artifacts';out.mkdir(exist_ok=True)
image=(ROOT/f'kernel_workspace/out-{variant}/arch/arm64/boot/Image').read_bytes()
marker=image.index(b'IKCFG_ST');config=zlib.decompress(image[marker+8:],16+zlib.MAX_WBITS).decode()
assert 'CONFIG_CRYPTO_OP13_LZ4=y' in config
assert b'lz4-op13' in image and b'lz4mid-op13' in image
assert sha(image)!='e4d541a769a98c94eebce2c1042f087be15162bd16f92c8ed528f8e985050eaf'
module={p.name:p.read_bytes() for p in sorted((ROOT/'modules/op13_memory').iterdir()) if p.is_file()}
module['ab-install']=b'Use the reviewed ab-stock profile on next boot.\n'
module['README.md']=(ROOT/'docs/OP13-ZRAM-AB.md').read_bytes()
module_name='OP13_Memory_Companion_v1.1.0_ZRAM_AB_TEST_ONLY.zip'
base.archive(out/module_name,module)
source=out/f'AK3_OP13_BakaSU_V2_{variant}_6.6.118_TEST_ONLY.zip'
with zipfile.ZipFile(source) as z:payload={n:z.read(n) for n in z.namelist()}
assert payload['Image']==image
script=payload['anykernel.sh'].decode();assert script.count('split_boot\n')==1
module_hash=sha((out/module_name).read_bytes())
preflight=f'''[ -x /data/adb/ksud ] || abort "BakaSU ksud required"
module_hash="$(/system/bin/toybox sha256sum "$AKHOME/companion.zip")"
[ "${{module_hash%% *}}" = "{module_hash}" ] || abort "Companion checksum mismatch"
ui_print "ZRAM AB: original LZ4 / LZ4 1.10.0 / MID2; 1x logical capacity"
'''
script=script.replace('split_boot\n',preflight+'split_boot || abort "Boot inspection failed"\n')
script=script.replace('    write_boot\n','    write_boot || abort "Boot write failed"\n')
script=script.replace('    flash_boot\n','    flash_boot || abort "Boot write failed"\n')
script+='''
if ! /data/adb/ksud module install "$AKHOME/companion.zip"; then
    abort "Kernel write returned success, companion install failed; inspect logs"
fi
ui_print "Test kernel and companion installed; reboot and verify actual profile."
'''
manifest={'kernel_recompiled':True,'variant':variant,'Image_sha256':sha(image),'module_sha256':module_hash,
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
          'boot_tested':False,'system_zram_ab_tested':False,
          'profiles':{'ab-stock':'lz4','ab-lz4':'lz4-op13','ab-mid':'lz4mid-op13'},
          'capacity_percent_MemTotal':100,'swappiness':100,'page_cluster':0,'watermark_scale_factor':200}
payload['anykernel.sh']=script.encode();payload['companion.zip']=(out/module_name).read_bytes()
payload['zram-ab-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
payload['ZRAM-AB-README.md']=module['README.md']
bundle=out/'AK3_OP13_BakaSU_ZRAM_AB_v1_TEST_ONLY.zip'
base.archive(bundle,payload)
assert b'PATCH_VBMETA_FLAG=0' in payload['anykernel.sh']
assert b'NO_VBMETA_PARTITION_PATCH=1' in payload['anykernel.sh']
assert 'vendor_boot' not in script and 'init_boot' not in script
(out/'zram-ab-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
print(json.dumps({'bundle':bundle.name,'sha256':sha(bundle.read_bytes()),**manifest}))
