"""오오카미 PS2 WOLVES.FST의 64비트 레코드.

하위 6비트: 종류, 6..13/32..45: 64바이트 정렬 크기,
14..31: 문자열 오프셋, 46..63: AFS 전역 항목 번호.
256MiB 이상 스트리밍 파일 4개는 크기 필드가 0이다.
"""
import struct
SIZE_MASK=0x3fc0|(0x3fff<<32)
def records(data):
    assert data[:4]==b'FST\0'
    strings,start=struct.unpack_from('<II',data,8)
    for p in range(start,len(data)-7,8):
        q=struct.unpack_from('<Q',data,p)[0]
        typ=q&63
        if typ==0:break
        no=(q>>14)&0x3ffff
        end=data.find(b'\0',strings+no)
        assert end>=strings+no
        yield dict(pos=p,raw=q,type=typ,name=data[strings+no:end].decode('ascii'),index=q>>46,size=(q&0x3fc0)+(((q>>32)&0x3fff)<<14))
def update_sizes(data,changes):
    out=bytearray(data);found=set()
    for r in records(data):
        if r['type']!=2 or r['index'] not in changes:continue
        size=(changes[r['index']]+63)&~63
        assert size<0x10000000
        q=(r['raw']&~SIZE_MASK)|(size&0x3fc0)|((size>>14)<<32)
        struct.pack_into('<Q',out,r['pos'],q);found.add(r['index'])
    assert found==set(changes)
    return bytes(out)
def audit(data,entries):
    seen=set();stream=[]
    for r in records(data):
        if r['type']!=2:continue
        i=r['index'];assert i not in seen;seen.add(i)
        name,offset,size=entries[i]
        expected=(size+63)&~63
        if expected>=0x10000000:expected=0;stream.append(i)
        assert r['size']==expected,(i,r['name'],r['size'],size)
    assert seen==set(range(len(entries)))
    return dict(file_records=len(seen),large_stream_files=stream,size_fields_verified=True)
if __name__=='__main__':
    import afs,json
    from pathlib import Path
    with open(afs.ISO,'rb') as f:f.seek(3188*2048);data=f.read(71672)
    report=audit(data,afs.toc(0)[0]+afs.toc(1)[0])
    patched=update_sizes(data,{804:169888})
    test=afs.toc(0)[0]+afs.toc(1)[0];name,off,_=test[804];test[804]=(name,off,169888)
    audit(patched,test)
    changed=[i for i,(a,b) in enumerate(zip(data,patched)) if a!=b]
    target=next(r for r in records(data) if r['type']==2 and r['index']==804)
    assert all(target['pos']<=i<target['pos']+8 for i in changed)
    report.update(prototype_size_update_verified=True,changed_bytes=len(changed),prototype_only=True)
    Path('work/fst_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
