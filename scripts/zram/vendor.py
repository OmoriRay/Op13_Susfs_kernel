#!/usr/bin/env python3
"""Vendor pinned LZ4 with auditable kernel includes and private symbols."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / 'scripts/extreme/sources.json').read_text())['lz4_op13']
COMMIT = LOCK['commit']
SHA256 = LOCK['sha256']
URL = 'https://codeload.github.com/lz4/lz4/tar.gz/' + COMMIT

def vendor(archive, destination):
    raw = archive.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256
    sources = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
        for member in tar:
            rel = '/'.join(Path(member.name).parts[1:])
            if rel in ['lib/lz4.c', 'lib/lz4.h', 'lib/lz4hc.c', 'lib/lz4hc.h', 'lib/LICENSE']:
                assert member.isfile()
                sources[Path(rel).name] = tar.extractfile(member).read().decode('utf-8')
    assert len(sources) == 5
    destination.mkdir(parents=True, exist_ok=True)
    names = set()
    records = []
    for name, text in sources.items():
        original = text.encode()
        names.update(re.findall(r'\b(LZ4_[a-z][A-Za-z0-9_]*)\s*\(', text))
        for header, kernel in [('stddef.h', 'linux/types.h'), ('limits.h', 'linux/limits.h'), ('string.h', 'linux/string.h')]:
            text = re.sub(r'^([ \t]*#\s*)include <' + re.escape(header) + r'>[^\n]*',
                          '#ifdef __KERNEL__\n# include <' + kernel + '>\n#else\n# include <' + header + '>\n#endif', text, flags=re.M)
        lines = []
        for line in text.splitlines():
            if line.startswith('#if defined(__cplusplus) || (defined (__STDC_VERSION__)'):
                line = '#if !defined(__KERNEL__) && (' + line[4:] + ')'
            lines.append(line)
        text = '\n'.join(lines) + '\n'
        (destination / name).write_text(text, encoding='utf-8', newline='\n')
        records.append({'file': name, 'upstream_sha256': hashlib.sha256(original).hexdigest(),
                        'ported_sha256': hashlib.sha256(text.encode()).hexdigest()})
    names -= {'LZ4_memcpy', 'LZ4_memmove', 'LZ4_memset'}
    names |= {'LZ4_malloc', 'LZ4_calloc', 'LZ4_free'}
    header = '/* Generated private namespace; never EXPORT_SYMBOL these APIs. */\n'
    header += ''.join('#define ' + n + ' op13_' + n + '\n' for n in sorted(names))
    (destination / 'namespace.h').write_text(header, encoding='utf-8', newline='\n')
    for p in sorted((ROOT / 'kernel/op13_lz4').iterdir()):
        if p.is_file(): shutil.copyfile(p, destination / p.name)
    manifest = {'repository': 'https://github.com/lz4/lz4', 'commit': COMMIT,
                'archive_sha256': SHA256, 'files': records, 'namespace_symbols': sorted(names),
                'glue_files': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'kernel/op13_lz4').iterdir()) if p.is_file()},
                'namespace_sha256': hashlib.sha256(header.encode()).hexdigest(),
                'changes': ['kernel-only C library includes/types', 'private symbol namespace',
                            'heap helpers use kernel allocators; per-page path uses preallocated state'],
                'kernel_boot_tested': False}
    (destination / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--dest', type=Path, required=True)
    args = parser.parse_args()
    archive = args.archive or ROOT / 'kernel_workspace/lz4-op13.tar.gz'
    if not archive.exists():
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(urllib.request.urlopen(URL, timeout=120).read())
    result = vendor(archive, args.dest)
    print(json.dumps({'commit': COMMIT, 'files': len(result['files']), 'symbols': len(result['namespace_symbols'])}))

if __name__ == '__main__': main()
