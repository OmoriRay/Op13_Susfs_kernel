#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
vendor=a.out/'vendor'
subprocess.run([sys.executable,str(ROOT/'scripts/zram/vendor.py'),'--archive',str(a.archive),'--dest',str(vendor)],check=True)
exe=a.out/'codec-test-asan'
cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',
     '-DOP13_CODEC_HOST_TEST=1','-Wall','-Wextra','-Werror','-I'+str(vendor),'-include',str(vendor/'compat.h'),
     str(ROOT/'tests/zram/codec_test.c'),*[str(vendor/x) for x in ('codec.c','support.c','lz4.c','lz4hc.c')],'-ldl','-o',str(exe)]
(a.out/'compile-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
subprocess.run(cmd,check=True)
r=subprocess.run([str(exe)],text=True,capture_output=True)
(a.out/'stdout.json').write_text(r.stdout);(a.out/'stderr.txt').write_text(r.stderr)
assert r.returncode==0,(r.returncode,r.stdout,r.stderr)
result=json.loads(r.stdout);assert result['state_reuse_roundtrips']==200000
print(json.dumps(result))
