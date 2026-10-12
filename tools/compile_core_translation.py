"""직접 작성한 공통 이름/항목 번역을 메시지 키에 연결한다."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
source={r['message']:r for r in rows if r['file']=='core.bin'}
out={}
for line in (ROOT/'translation/core_manual.txt').read_text(encoding='utf-8').splitlines():
    number,text=line.split(' ',1);i=int(number);r=source[i]
    assert r['source'].endswith('<8001>') and r['source'].count('<')==1
    assert r['id'] not in out
    out[r['id']]=text+'<8001>'
(ROOT/'translation/core_ko.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print('공통 명칭 직접 번역:',len(out))
