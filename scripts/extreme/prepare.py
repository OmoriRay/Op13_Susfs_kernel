#!/usr/bin/env python3
"""Prepare the pinned OEM tree; conflicting upstream changes are never guessed."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

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

def main():
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

if __name__=='__main__':
    try:main()
    except Exception as e:
        REPORT.mkdir(exist_ok=True)
        (REPORT/'failure.txt').write_text(str(e)+'\n')
        raise
