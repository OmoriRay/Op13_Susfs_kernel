#!/usr/bin/env python3
"""Prepare the pinned OEM tree; conflicting upstream changes are never guessed."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[2]
WORK=ROOT/'kernel_workspace'
REPORT=ROOT/'reports'
LOCK=json.loads((Path(__file__).with_name('sources.json')).read_text())

def run(*args,cwd=None,check=True):
    print('+',*map(str,args),flush=True)
    return subprocess.run(list(map(str,args)),cwd=cwd,check=check)

def output(*args,cwd=None):
    return subprocess.check_output(list(map(str,args)),cwd=cwd)

def checkout(repo,sha,path):
    path.mkdir(parents=True,exist_ok=True)
    if not (path/'.git').exists():
        run('git','init','-q',path)
        run('git','remote','add','origin',repo,cwd=path)
        run('git','config','user.name','OP13 Build',cwd=path)
        run('git','config','user.email','build@invalid.local',cwd=path)
    run('git','fetch','--depth=1','origin',sha,cwd=path)
    run('git','checkout','--detach','FETCH_HEAD',cwd=path)
    assert output('git','rev-parse','HEAD',cwd=path).decode().strip()==sha

def resolve_conflicts(tree,kind):
    entries={}
    for line in output('git','ls-files','-u',cwd=tree).decode().splitlines():
        fields,path=line.split('\t',1)
        mode,sha,stage=fields.split()
        entries.setdefault(path,{})[stage]={'sha':sha,'mode':mode}
    if not entries:
        return
    unresolved=[]
    for path,stages in entries.items():
        source=ROOT/'patches'/'extreme'/f'{kind}-resolutions'/path
        metadata=source.with_name(source.name+'.json')
        if source.is_file() and metadata.is_file():
            expected=json.loads(metadata.read_text())
            assert expected==stages, f'Stale resolution: {path}'
            shutil.copyfile(source,tree/path)
            run('git','add','--',path,cwd=tree)
            continue
        unresolved.append(path)
        for stage,label in [('1','BASE'),('2','OEM'),('3','UPSTREAM')]:
            if stage in stages:
                p=REPORT/'conflicts'/kind/(path+'.'+label)
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(output('git','cat-file','blob',stages[stage]['sha'],cwd=tree))
        p=REPORT/'conflicts'/kind/(path+'.MERGED')
        p.parent.mkdir(parents=True,exist_ok=True)
        if (tree/path).is_file():shutil.copyfile(tree/path,p)
    (REPORT/f'{kind}-conflicts.json').write_text(json.dumps(entries,indent=2))
    if unresolved:
        raise RuntimeError(f'{kind}: {len(unresolved)} source conflicts require explicit review; see reports/conflicts')

def lts_audit():
    WORK.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).with_name('sources.json'),REPORT/'sources.json')
    common=WORK/'common'
    checkout(LOCK['common']['repo'],LOCK['common']['commit'],common)
    stable=WORK/'stable.git'
    if not stable.exists():run('git','init','--bare','-q',stable)
    run('git','--git-dir',stable,'fetch','--depth=1',LOCK['linux']['repo'],
        LOCK['linux']['base']+':refs/heads/base',LOCK['linux']['target']+':refs/heads/target')
    patch=REPORT/'linux-6.6.118-to-6.6.161.patch'
    patch.write_bytes(output('git','--git-dir',stable,'diff','--binary','refs/heads/base','refs/heads/target'))
    alternate=common/'.git/objects/info/alternates';alternate.parent.mkdir(exist_ok=True)
    alternate.write_text(str(stable/'objects')+'\n')
    result=run('git','apply','--3way','--whitespace=nowarn',patch,cwd=common,check=False)
    resolve_conflicts(common,'lts')
    if result.returncode and not output('git','diff','--cached','--name-only',cwd=common):
        raise RuntimeError('LTS application failed without an applied index')
    run('git','diff','--check',cwd=common)
    run('git','add','-A',cwd=common)
    run('git','commit','-qm','Integrate reviewed Linux 6.6.161 updates',cwd=common)
    (REPORT/'lts-oem.patch').write_bytes(output('git','diff',LOCK['common']['commit'],'HEAD',cwd=common))
    print('LTS source preparation complete',flush=True)

def apply(tree,name):
    patch=ROOT/'patches/extreme'/name
    run('git','apply','--check','--whitespace=error-all',patch,cwd=tree)
    run('git','apply','--whitespace=error-all',patch,cwd=tree)

def main():
    WORK.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__).with_name('sources.json'),REPORT/'sources.json')
    common=WORK/'common'
    checkout(LOCK['common']['repo'],LOCK['common']['commit'],common)
    baka=WORK/'BakaSU'
    run('git','clone',LOCK['bakasu']['repo'],baka)
    run('git','checkout','--detach',LOCK['bakasu']['commit'],cwd=baka)
    assert output('git','rev-parse','HEAD',cwd=baka).decode().strip()==LOCK['bakasu']['commit']
    assert int(output('git','rev-list','--count','HEAD',cwd=baka))+30700==35257
    archive=WORK/'susfs.tar.gz'
    run('curl','--fail','--location','--retry','3','--silent','--show-error',LOCK['susfs']['archive'],'-o',archive)
    assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==LOCK['susfs']['sha256']
    susfs=WORK/'susfs';susfs.mkdir()
    with tarfile.open(archive) as t:
        for member in t:
            if member.isdir():continue
            if not member.isfile():raise RuntimeError('Unexpected non-regular SUSFS archive entry')
            rel=Path(*Path(member.name).parts[1:]);target=susfs/rel
            assert target.resolve().is_relative_to(susfs.resolve())
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(t.extractfile(member).read())
    for path in ['fs/susfs.c','include/linux/susfs.h','include/linux/susfs_def.h']:
        shutil.copyfile(susfs/'kernel_patches'/path,common/path)
    link=common/'drivers/kernelsu'
    assert not link.exists()
    link.symlink_to(os.path.relpath(baka/'kernel',link.parent),target_is_directory=True)
    p=common/'drivers/Makefile';p.write_text(p.read_text()+'\nobj-$(CONFIG_KSU) += kernelsu/\n')
    p=common/'drivers/Kconfig';text=p.read_text();pos=text.rfind('endmenu')
    assert pos>=0;p.write_text(text[:pos]+'source "drivers/kernelsu/Kconfig"\n\n'+text[pos:])
    apply(common,'0001-susfs-c7f670f5-oem118.patch')
    apply(baka,'0002-bakasu-priority-uid.patch')
    apply(common,'0003-o3-and-configurable-64k-mthp.patch')
    run(sys.executable,ROOT/'scripts/zram/integrate.py','--tree',common)
    assert 'ksu_selinux_hide_running' not in (common/'security/selinux/hooks.c').read_text()
    assert 'CMD_SUSFS_SET_PRIORITY_UID_FILTER' in (baka/'kernel/supercall/dispatch.c').read_text()
    for tree in (common,baka):run('git','diff','--check',cwd=tree)
    rejects=list(common.rglob('*.rej'))
    assert not rejects,rejects
    version={'actual_kernel':'6.6.118','lts_target':'6.6.161','lts_status':'not_merged_130_conflicting_OEM_Android_files',
             'lts_audit_run':41858601891,'bakasu':LOCK['bakasu'],'susfs':LOCK['susfs']['commit'],
             'selinux_hide_owner':'BakaSU; SUSFS native hooks/selinuxfs/services/status sections excluded together',
             'vendor_module_ABI_verified':False,'boot_tested':False,'performance_tested':False}
    (REPORT/'source-version.json').write_text(json.dumps(version,indent=2))
    manifests=[]
    for patch in sorted((ROOT/'patches/extreme').glob('*.patch')):
        manifests.append({'file':patch.name,'sha256':hashlib.file_digest(patch.open('rb'),'sha256').hexdigest(),
                          'applied_in_prepare':patch.name.startswith(('0001-','0002-','0003-')),
                          'applied_in_build':patch.name.startswith('0004-'),
                          'applied_in_lab_max_only':patch.name.startswith('0100-')})
    (REPORT/'patches.json').write_text(json.dumps(manifests,indent=2))
    (REPORT/'common-changes.patch').write_bytes(output('git','diff','--binary',cwd=common))
    (REPORT/'bakasu-changes.patch').write_bytes(output('git','diff','--binary',cwd=baka))
    run('tar','--zstd','-cf',ROOT/'prepared-sources.tar.zst','--exclude=common/.git','-C',WORK,'common','BakaSU','susfs')
    print('Pinned OEM 6.6.118 + current BakaSU/SUSFS + O3/mTHP sources prepared',flush=True)

if __name__=='__main__':
    try:
        if '--lts-audit' in sys.argv:lts_audit()
        else:main()
    except Exception as e:
        REPORT.mkdir(exist_ok=True)
        (REPORT/'failure.txt').write_text(str(e)+'\n')
        raise
