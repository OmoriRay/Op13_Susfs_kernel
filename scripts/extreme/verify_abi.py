#!/usr/bin/env python3
"""Check sampled vendor imports; unknown vendor-to-vendor exports stay unknown."""
import json,sys
from pathlib import Path

root=Path(__file__).resolve().parents[2];variant=sys.argv[1]
symbols={}
for line in (root/'kernel_workspace'/('out-'+variant)/'Module.symvers').read_text().splitlines():
    fields=line.split()
    if len(fields)>=3:symbols[fields[1]]={'crc':int(fields[0],16),'provider':fields[2]}
samples=json.loads((Path(__file__).with_name('vendor-imports.json')).read_text())
results=[];mismatches=[];matched=0;unknown=0
for module in samples['modules']:
    items=[]
    for entry in module['imports']:
        name=entry['symbol'];candidate=symbols.get(name)
        if candidate is None:
            unknown+=1;items.append({'symbol':name,'status':'provider_not_in_this_build'})
        elif candidate['crc']==int(entry['crc'],16):matched+=1
        else:
            item={'module':module['filename'],'symbol':name,'expected':entry['crc'],
                  'actual':hex(candidate['crc']),'provider':candidate['provider']}
            mismatches.append(item);items.append(dict(item,status='crc_mismatch'))
    results.append({'module':module['filename'],'imports':len(module['imports']),'details':items})
report={'scope':samples['scope'],'matching_import_records':matched,'unknown_provider_records':unknown,
        'mismatching_import_records':len(mismatches),'mismatches':mismatches,'modules':results,
        'full_ABI_compatibility_proven':False,'vermagic_note':'GKI module version rules require separate runtime evaluation'}
dest=root/'reports'/variant/'vendor-abi-sample-check.json';dest.write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ['modules','mismatches']}))
if mismatches:print(json.dumps(mismatches,indent=2))
if mismatches:raise SystemExit('Known vendor symbol CRC mismatches: packaging blocked; see ABI sample report')
