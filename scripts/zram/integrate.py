#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vendor import vendor, URL
import urllib.request

def main():
    p=argparse.ArgumentParser();p.add_argument('--tree',type=Path,required=True);a=p.parse_args()
    tree=a.tree
    files=['lib/Makefile','crypto/Kconfig','drivers/block/zram/zcomp.c']
    original={name:(tree/name).read_text(encoding='utf-8') for name in files}
    marker='#if IS_ENABLED(CONFIG_CRYPTO_LZ4HC)'
    assert 'op13_lz4/' not in original['lib/Makefile']
    assert 'lib/op13_lz4/Kconfig' not in original['crypto/Kconfig']
    assert original['crypto/Kconfig'].rfind('endmenu')>=0
    assert original['drivers/block/zram/zcomp.c'].count(marker)==1
    archive=tree.parent/'lz4-op13.tar.gz'
    if not archive.exists():archive.write_bytes(urllib.request.urlopen(URL,timeout=120).read())
    manifest=vendor(archive,tree/'lib/op13_lz4')
    path=tree/'lib/Makefile'
    text=original['lib/Makefile']
    path.write_text(text+'\nobj-$(CONFIG_CRYPTO_OP13_LZ4) += op13_lz4/\n',encoding='utf-8',newline='\n')
    path=tree/'crypto/Kconfig'
    text=original['crypto/Kconfig']
    pos=text.rfind('endmenu');assert pos>=0
    path.write_text(text[:pos]+'source "lib/op13_lz4/Kconfig"\n\n'+text[pos:],encoding='utf-8',newline='\n')
    path=tree/'drivers/block/zram/zcomp.c'
    text=original['drivers/block/zram/zcomp.c']
    text=text.replace(marker,'#if IS_ENABLED(CONFIG_CRYPTO_OP13_LZ4)\n\t"lz4-op13",\n\t"lz4mid-op13",\n#endif\n'+marker)
    path.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'op13_lz4_commit':manifest['commit'],'backend_names':['lz4-op13','lz4mid-op13']}))

if __name__=='__main__':main()
