"""직접 번역한 원문과 제어 코드가 완전히 같은 복제 메시지에만 적용."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
source={r['id']:r['source'] for r in rows};manual={};by_source={}
for p in sorted((ROOT/'translation').glob('*_ko.json')):
    if p.name=='exact_duplicates_ko.json':continue
    for key,value in json.loads(p.read_text(encoding='utf-8')).items():
        assert key not in manual,key
        manual[key]=value
        if source[key] in by_source and by_source[source[key]]!=value:
            # 문맥별 번역이 다른 원문은 자동 확장하지 않는다.
            by_source[source[key]]=None
        else:by_source[source[key]]=value
out={r['id']:by_source[r['source']] for r in rows if r['id'] not in manual and by_source.get(r['source']) is not None}
# 문장 구간이 모두 같은 대사는 다른 동작/카메라 코드도 원본 그대로 두고 재사용한다.
rx=re.compile(r'(<[0-9A-F]{4}(?:,[0-9A-F]{4})*>)')
by_segments={};conflicts=set()
for key,value in manual.items():
    sp=[s for s in rx.split(source[key]) if s and not rx.fullmatch(s)]
    tp=[s for s in rx.split(value) if s and not rx.fullmatch(s)]
    if len(sp)!=len(tp):continue
    sig=tuple(s.strip() for s in sp)
    if not any(sig):continue
    if sig in by_segments and by_segments[sig]!=tp:conflicts.add(sig)
    else:by_segments[sig]=tp
for r in rows:
    if r['id'] in manual or r['id'] in out:continue
    parts=rx.split(r['source']);ix=[i for i,s in enumerate(parts) if s and not rx.fullmatch(s)]
    sig=tuple(parts[i].strip() for i in ix)
    if sig in conflicts or sig not in by_segments:continue
    for i,t in zip(ix,by_segments[sig]):parts[i]=t
    out[r['id']]=''.join(parts)
(ROOT/'translation/exact_duplicates_ko.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('문장 구간이 동일하며 원본 제어 코드를 보존한 재사용 메시지:',len(out))
