"""중복 파일명과 대용량 파일을 빠뜨리지 않는 AFS 원본 조사."""
from pathlib import Path
import struct,json,pickle,hashlib,collections
import afs,pack,collect,fixed_records
ROOT=Path(__file__).resolve().parents[1]
def main():
    records=[];blocks=[];extra_blocks=[];errors=[]
    with open(afs.ISO,'rb') as f:
        for k in (0,1):
            toc,nt,ent=afs.toc(k)
            for i,(name,off,size) in enumerate(toc):
                base=afs.AFS_LBA[k]*2048+off
                f.seek(base);head=f.read(min(size,32784))
                rec=dict(archive=k,index=i,name=name,offset=off,size=size,magic=head[:16].hex())
                records.append(rec)
                # 헤더의 오프셋 검사는 전체 길이를 사용한다.
                if len(head)<8:continue
                n=struct.unpack_from('<I',head)[0]
                if not 1<=n<=4096 or 4+8*n>size:continue
                offsets=struct.unpack_from(f'<{n}I',head,4)
                if not 4+8*n<=offsets[0]<=4+8*n+32:continue
                if offsets[-1]>size or any(a>b for a,b in zip(offsets,offsets[1:])):continue
                f.seek(base);data=f.read(size)
                for record,chunk in fixed_records.split(name,data):
                    for b in collect.find(chunk):
                        sub=collect.sub(chunk,b['path']);parts=pack.parse(sub)
                        b.update(file=name,archive=k,index=i,offset=off,size=size)
                        for typ in ('msd','msa','mst'):
                            j=b['i_'+typ];b[typ]=sub[parts[j][1]:parts[j][2]] if j is not None else None
                        if record is not None:
                            b.update(record=record,record_size=len(chunk))
                            b['mst']=fixed_records.trim_texture(b['mst'])
                        (extra_blocks if record else blocks).append(b)
    blocks.extend(extra_blocks)
    names=collections.Counter(r['name'] for r in records)
    old=pickle.loads((ROOT/'work/blocks.pkl').read_bytes())
    known={(b['file'],b['path'],hashlib.sha256(b['msd']).hexdigest()) for b in old}
    new=[{k:b[k] for k in ('file','archive','index','path')} for b in blocks if (b['file'],b['path'],hashlib.sha256(b['msd']).hexdigest()) not in known]
    report=dict(archive_entries=len(records),unique_names=len(names),duplicate_names={n:c for n,c in names.items() if c>1},old_blocks=len(old),all_blocks=len(blocks),previously_missing=new)
    (ROOT/'work/afs_inventory.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'work/archive_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'work/all_blocks.pkl').write_bytes(pickle.dumps(blocks))
    print(json.dumps({**report,'previously_missing_count':len(new),'previously_missing':new[:8]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
