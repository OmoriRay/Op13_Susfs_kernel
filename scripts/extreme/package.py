#!/usr/bin/env python3
import gzip,hashlib,json,shutil,struct,subprocess,sys,zipfile,zlib
from pathlib import Path

root=Path(__file__).resolve().parents[2];variant=sys.argv[1]
assert variant in ['extreme','lab-full-lto','lab-max']
lock=json.loads((root/'scripts/extreme/sources.json').read_text())
out=root/'kernel_workspace'/('out-'+variant);dest=root/'artifacts';dest.mkdir(exist_ok=True)
report=root/'reports'/variant
image=(out/'arch/arm64/boot/Image').read_bytes()
assert len(image)>10_000_000
assert image[56:60]==b'ARM\x64'
marker=image.index(b'IKCFG_ST')
embedded=zlib.decompress(image[marker+8:],16+zlib.MAX_WBITS).decode()
assert embedded==(out/'.config').read_text()
assert 'CONFIG_CC_OPTIMIZE_FOR_PERFORMANCE_O3=y' in embedded
assert 'CONFIG_KSU_SUSFS_PRIORITY_UID_FILTER=y' in embedded
for symbol in ['ksu_handle_susfs_cmd','susfs_set_priority_uid_filter']:
    assert symbol in (report/'integrated-symbols.txt').read_text()
ak3=root/'ak3_work'
subprocess.run(['git','clone',lock['ak3']['repo'],str(ak3)],check=True)
subprocess.run(['git','checkout','--detach',lock['ak3']['commit']],cwd=ak3,check=True)
actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ak3).decode().strip()
assert actual==lock['ak3']['commit']
script='''### AnyKernel3 Ramdisk Mod Script
properties() { '
kernel.string=PJZ110 BakaSU Extreme V2 - VARIANT
do.devicecheck=0
do.modules=0
do.systemless=0
do.cleanup=1
do.cleanuponabort=1
supported.versions=17
supported.patchlevels=2026-09 -
'; }
BLOCK=boot
IS_SLOT_DEVICE=auto
SLOT_SELECT=active
RAMDISK_COMPRESSION=auto
PATCH_VBMETA_FLAG=0
NO_VBMETA_PARTITION_PATCH=1
NO_MAGISK_CHECK=1
. tools/ak3-core.sh
[ "$(getprop ro.product.model)" = "PJZ110" ] || abort "Expected PJZ110"
[ "$(getprop ro.product.device)" = "OP5D0DL1" ] || abort "Expected OP5D0DL1"
[ "$(getprop ro.boot.slot_suffix)" = "_a" ] || abort "Expected reviewed active slot a"
[ "$(getprop ro.build.fingerprint)" = "OnePlus/PJZ110/OP5D0DL1:17/CP2A.260605.016/V.487427a-2227f32-224bc4c:user/release-keys" ] || abort "ROM differs from reviewed target"
case "$(uname -r)" in 6.6.*-android15-8-*-4k*) ;; *) abort "Expected android15-6.6 generation 8 / 4K" ;; esac
ui_print "BakaSU Extreme V2 - VARIANT"
ui_print "OEM 6.6.118; LLVM 23.1.5; O3; SUSFS c7f670f5"
ui_print "Experimental build; boot and vendor ABI verification pending"
split_boot
if [ -f "$SPLITIMG/ramdisk.cpio" ]; then
    unpack_ramdisk
    write_boot
else
    flash_boot
fi
'''.replace('VARIANT',variant)
(ak3/'anykernel.sh').write_text(script)
shutil.copyfile(out/'arch/arm64/boot/Image',ak3/'Image')
profile=json.loads((report/'profile.json').read_text())
profile['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip()
profile['Image_sha256']=hashlib.sha256(image).hexdigest()
profile['AnyKernel3_commit']=actual
profile['root_version_code']=35257;profile['uapi']=6
profile['susfs_commit']=lock['susfs']['commit']
(ak3/'build-manifest.json').write_text(json.dumps(profile,indent=2))
package=dest/f'AK3_OP13_BakaSU_V2_{variant}_6.6.118_TEST_ONLY.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for file in sorted(ak3.rglob('*')):
        rel=file.relative_to(ak3)
        if file.is_file() and not any(x in ['.git','.github'] for x in rel.parts) and rel.name!='README.md':
            z.write(file,str(rel))
with zipfile.ZipFile(package) as z:
    assert z.testzip() is None
    assert z.read('Image')==image
    assert not any('ramfix' in x or 'magisk.zip' in x for x in z.namelist())
    for forbidden in ['module install','resetprop','setprop ','am start','pm clear']:
        assert forbidden not in z.read('anykernel.sh').decode()
shutil.copyfile(out/'arch/arm64/boot/Image',dest/f'Image-{variant}')
helper=root/'kernel_workspace/susfs/ksu_module_susfs/tools/ksu_susfs_arm64'
blob=helper.read_bytes();assert blob[:4]==b'\x7fELF' and struct.unpack_from('<H',blob,18)[0]==183
shutil.copyfile(helper,dest/'ksu_susfs-c7f670f5-arm64')
(report/'package-manifest.json').write_text(json.dumps(profile,indent=2))
lines=[]
for p in sorted(dest.iterdir()):
    if p.is_file() and p.name!='SHA256SUMS':lines.append(hashlib.file_digest(p.open('rb'),'sha256').hexdigest()+'  '+p.name)
(dest/'SHA256SUMS').write_text('\n'.join(lines)+'\n')
print(package.name,hashlib.file_digest(package.open('rb'),'sha256').hexdigest())
