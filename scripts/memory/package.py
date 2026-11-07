#!/usr/bin/env python3
"""Build a separate companion and a matching AK3 bundle from a pinned Image.

This is a packaging build, not a new kernel compilation or device boot test.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads(Path(__file__).with_name('base-lock.json').read_text(encoding='utf-8'))
MODULE = ROOT / 'modules/op13_memory'


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def archive(path, payload):
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(payload.items()):
            assert not name.startswith('/') and '..' not in Path(name).parts
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0))
            info.create_system = 3
            executable = name.endswith('.sh') or name.startswith('META-INF/') or name.startswith('tools/')
            info.external_attr = (0o100755 if executable else 0o100644) << 16
            output.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as result:
        assert result.testzip() is None
        assert set(result.namelist()) == set(payload)
        for name, data in payload.items():
            assert result.read(name) == data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-commit', default=os.environ.get('GITHUB_SHA'))
    args = parser.parse_args()
    commit = args.source_commit or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit)
    args.out.mkdir(parents=True, exist_ok=True)
    original = (args.base / LOCK['base_package']).read_bytes()
    assert sha(original) == LOCK['base_package_sha256'], 'Unreviewed base AK3'
    with zipfile.ZipFile(args.base / LOCK['base_package']) as base:
        assert base.testzip() is None
        payload = {name: base.read(name) for name in base.namelist() if not name.endswith('/')}
    assert sha(payload['Image']) == LOCK['Image_sha256'], 'Unreviewed kernel Image'
    config = (args.base / 'final.config').read_text(encoding='utf-8')
    image = payload['Image']
    assert image[56:60] == b'ARM\x64'
    embedded = zlib.decompress(image[image.index(b'IKCFG_ST') + 8:], 16 + zlib.MAX_WBITS).decode()
    assert embedded == config, 'Configuration must match the pinned Image byte-for-byte'
    for flag in ('ZRAM', 'ZRAM_MULTI_COMP', 'ZRAM_WRITEBACK', 'ZRAM_TRACK_ENTRY_ACTIME', 'CRYPTO_LZ4', 'CRYPTO_ZSTD', 'LRU_GEN', 'PSI'):
        assert f'CONFIG_{flag}=y\n' in config, flag
    module_payload = {p.relative_to(MODULE).as_posix(): p.read_bytes() for p in MODULE.rglob('*') if p.is_file()}
    module_payload['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    module_payload['README.md'] = (ROOT / 'docs/OP13-Memory-Companion.md').read_bytes()
    for name in ('customize.sh', 'service.sh', 'memory.sh', 'x1-handoff.sh', 'uninstall.sh', 'module.prop', 'skip_mount'):
        assert name in module_payload
    manifest = {
        'schema': 1, 'integration_commit': commit, 'kernel': LOCK,
        'kernel_recompiled': False, 'kernel_Image_unchanged': True,
        'new_bundle_device_tested': False, 'performance_tested': False,
        'module_id': 'op13_memory', 'module_version': '1.0.0-experimental',
        'module_files': {name: sha(data) for name, data in sorted(module_payload.items())},
        'profiles': {
            'pandora_like': {'primary': 'lz4', 'capacity_percent_MemTotal': 200, 'swappiness': 100, 'page_cluster': 0, 'watermark_scale_factor': 200, 'min_ttl_ms': 1000},
            'density': {'primary': 'zstd', 'capacity_percent_MemTotal': 200, 'swappiness': 100, 'page_cluster': 0, 'watermark_scale_factor': 200, 'min_ttl_ms': 1000},
            'game': {'primary': 'lz4', 'capacity_percent_MemTotal': 100, 'swappiness': 60, 'page_cluster': 0, 'watermark_scale_factor': 150, 'min_ttl_ms': 1000},
        },
        'recompression': 'ZSTD secondary configured before initialization when supported; no automatic recompression worker in v1',
        'writeback': 'Not configured; an existing backing device blocks takeover',
        'x1_handoff': 'Reviewed 2.13.0 only, guarded zram_apply and ram_expand_apply; original-file backups retained',
    }
    module_name = 'OP13_Memory_Companion_v1.0.0_TEST_ONLY.zip'
    module_path = args.out / module_name
    archive(module_path, module_payload)
    manifest['module_zip_sha256'] = sha(module_path.read_bytes())
    original_script = payload['anykernel.sh'].decode()
    assert 'module install' not in original_script and original_script.count('split_boot\n') == 1
    preflight = f'''# OP13 Memory Companion bundle preflight (no ZRAM writes here).
[ -x /data/adb/ksud ] || abort "BakaSU ksud is required for the bundled companion"
[ -x /system/bin/toybox ] || abort "System Toybox is required"
/system/bin/toybox swapon --help 2>&1 | grep -q -- '-p' || abort "Toybox swapon priority support required"
[ -r /sys/block/zram0/comp_algorithm ] || abort "ZRAM interface missing"
module_hash="$(/system/bin/toybox sha256sum "$AKHOME/companion.zip")"
[ "${{module_hash%% *}}" = "{manifest['module_zip_sha256']}" ] || abort "Companion checksum mismatch"
ui_print "Memory companion: LZ4, 2x MemTotal, swappiness 100; experimental"
ui_print "Known base-kernel warnings remain; this bundle is not device-validated"
'''
    updated = original_script.replace('split_boot\n', preflight + 'split_boot\n')
    updated = updated.replace('split_boot\n', 'split_boot || abort "Boot image inspection failed"\n')
    updated = updated.replace('    write_boot\n', '    write_boot || abort "Boot write failed; companion not installed"\n')
    updated = updated.replace('    flash_boot\n', '    flash_boot || abort "Boot write failed; companion not installed"\n')
    updated += '''
# Install the paired module only after the boot write has returned successfully.
# A failed companion install must be reported, never mistaken for full success.
ui_print "Installing paired OP13 Memory Companion"
if ! /data/adb/ksud module install "$AKHOME/companion.zip"; then
    abort "Kernel write completed, but companion installation failed; inspect manager logs"
fi
ui_print "Kernel and companion installed. Reboot; verify /proc/swaps and SwapTotal."
'''
    payload['anykernel.sh'] = updated.encode()
    payload['companion.zip'] = module_path.read_bytes()
    payload['memory-manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    payload['MEMORY-README.md'] = (ROOT / 'docs/OP13-Memory-Companion.md').read_bytes()
    name = 'AK3_OP13_BakaSU_lab-thin-max_Memory-v1.0.0_TEST_ONLY.zip'
    archive(args.out / name, payload)
    assert b'PATCH_VBMETA_FLAG=0' in payload['anykernel.sh']
    assert b'NO_VBMETA_PARTITION_PATCH=1' in payload['anykernel.sh']
    assert b'ramfix' not in payload['anykernel.sh'].lower()
    (args.out / 'memory-manifest.json').write_bytes(payload['memory-manifest.json'])
    (args.out / 'base-lock.json').write_text(json.dumps(LOCK, indent=2) + '\n', encoding='utf-8')
    (args.out / 'source-audit.json').write_bytes(Path(__file__).with_name('source-audit.json').read_bytes())
    for label in ('final.config', 'compiler-command-checks.json', 'vendor-abi-sample-check.json'):
        (args.out / label).write_bytes((args.base / label).read_bytes())
    checks = [f'{sha(p.read_bytes())}  {p.name}' for p in sorted(args.out.iterdir()) if p.is_file() and p.name != 'SHA256SUMS.txt']
    (args.out / 'SHA256SUMS.txt').write_text('\n'.join(checks) + '\n', encoding='utf-8')
    print(json.dumps({'bundle': name, 'bundle_sha256': sha((args.out / name).read_bytes()), 'module': module_name, 'module_sha256': manifest['module_zip_sha256'], 'Image_sha256': sha(payload['Image']), 'kernel_recompiled': False, 'device_tested': False}))


if __name__ == '__main__':
    main()
