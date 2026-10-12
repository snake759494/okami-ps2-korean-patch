"""모든 AFS 항목의 중첩 컨테이너를 헤더로 조사한다. 이미지 일본어 판정은 별도 검수한다."""
from pathlib import Path
from collections import Counter
import json,pickle,struct
import afs,fixed_records

ROOT=Path(__file__).resolve().parents[1]
blocks=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes())
fonts={(b['archive'],b['index'],((f"record{b['record']}",) if b.get('record',0) else ())+tuple(b['path'])+(b['i_mst'],)) for b in blocks if b['i_mst'] is not None}
leaves=[]

def walk(f,archive,index,name,absolute,size,path=(),tag=''):
    f.seek(absolute);head=f.read(min(size,32784))
    children=None
    if len(head)>=8:
        count=struct.unpack_from('<I',head)[0]
        if 1<=count<=4096 and 4+8*count<=len(head):
            offsets=list(struct.unpack_from(f'<{count}I',head,4))
            tags=[head[4+4*count+4*i:8+4*count+4*i].rstrip(b'\0') for i in range(count)]
            if (4+8*count<=offsets[0]<=4+8*count+32 and offsets[-1]<=size
                and all(a<=b for a,b in zip(offsets,offsets[1:]))
                and all(t and all(32<=v<127 for v in t) for t in tags)):
                children=list(zip(offsets,offsets[1:]+[size],tags))
    if children and len(path)<24:
        for i,(a,z,t) in enumerate(children):walk(f,archive,index,name,absolute+a,z-a,path+(i,),t.decode('ascii'))
        return
    magic=head[:4]
    font=(archive,index,path) in fonts
    if font:kind='message_font'
    elif magic in (b'TIM2',b'TIM3'):kind='texture'
    elif magic==b'\x00\x00\x01\xba' or name.lower().endswith(('.pss','.mpg','.m2v')):kind='video_candidate'
    else:kind='unclassified'
    leaves.append(dict(id=f'{archive}:{index:04d}:'+('.'.join(map(str,path)) or 'root'),archive=archive,index=index,file=name,path=list(path),tag=tag,iso_offset=absolute,size=size,magic=head[:16].hex(),kind=kind,review_status='not_reviewed',japanese_text=None))

with open(afs.ISO,'rb') as f:
    for archive in (0,1):
        for index,(name,offset,size) in enumerate(afs.toc(archive)[0]):
            base=afs.AFS_LBA[archive]*2048+offset
            if name in fixed_records.LAYOUT:
                stride,count=fixed_records.LAYOUT[name]
                assert size==stride*count
                for record in range(count):walk(f,archive,index,name,base+stride*record,stride,() if not record else (f'record{record}',))
            else:walk(f,archive,index,name,base,size)

report=dict(complete=False,scope='전체 AFS 항목의 파싱 가능한 중첩 컨테이너 잎 노드. 미분류 항목 안의 압축/복합 이미지와 ELF/영상 내 문자는 추가 조사 필요.',leaf_count=len(leaves),kinds=dict(Counter(r['kind'] for r in leaves)),tags=dict(Counter(r['tag'] for r in leaves)),resources=leaves)
dest=ROOT/'work/visual_resource_inventory.json';dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('resources','tags')},ensure_ascii=False,indent=2))
print('주요 태그:',Counter(r['tag'] for r in leaves).most_common(30))
