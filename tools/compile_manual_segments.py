"""직접 작성한 문장 구간만 치환하고 원본 제어 토큰과 인수를 보존한다."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
source={r['id']:r['source'] for r in rows}
rx=re.compile(r'(<[0-9A-F]{4}(?:,[0-9A-F]{4})*>)')
for path in sorted((ROOT/'translation').glob('segments_*.txt')):
    out={}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):continue
        key,text=line.split(' ',1);parts=rx.split(source[key]);indices=[i for i,p in enumerate(parts) if p and not rx.fullmatch(p)]
        tr=text.split('|');assert len(indices)==len(tr),(key,len(indices),len(tr),parts)
        for i,t in zip(indices,tr):parts[i]=t
        assert key not in out;out[key]=''.join(parts)
    dest=path.with_name(path.stem+'_ko.json');dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(path.name,len(out))
