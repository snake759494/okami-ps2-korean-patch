"""번역 누락/제어 토큰 변경을 탐지한다. 미완성 상태는 성공으로 반환하지 않는다."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
    mapping={};errors=[]
    for p in sorted((ROOT/'translation').glob('*_ko.json')):
        for k,v in json.loads(p.read_text(encoding='utf-8')).items():
            if k in mapping:errors.append(['중복 번역 키',k])
            mapping[k]=v
    source={r['id']:r for r in rows};token=re.compile(r'<[0-9A-F]{4}(?:,[0-9A-F]{4})*>')
    for k,v in mapping.items():
        if k not in source:errors.append(['존재하지 않는 메시지',k]);continue
        if token.findall(source[k]['source'])!=token.findall(v):errors.append(['제어 토큰 불일치',k])
        if re.search('[ぁ-ヿ]',v):errors.append(['일본어 가나 잔존',k])
        visible=token.sub('',v)
        if not re.search('[가-힣]',v) and re.search(r'[^\s.…?？!！・:：]',visible):errors.append(['한국어 번역 없음',k])
    # 공통 글리프 목록 7개와 본문이 전혀 없는 제어 전용 메시지는 번역 대상이 아니다.
    # 일본어 본문이나 OCR이 불확실한 기호를 자동 제외하지 않는다.
    preserved={r['id']:('공통 글리프 목록' if r['file']=='core.bin' else '본문 없는 제어 메시지')
               for r in rows if (r['file']=='core.bin' and r['message']<7) or token.sub('',r['source'])==''}
    overlap=set(preserved)&set(mapping)
    if overlap:errors.append(['보존 대상에 번역 지정',sorted(overlap)])
    untranslated=[r['id'] for r in rows if r['id'] not in mapping and r['id'] not in preserved]
    report=dict(status='통과' if not errors and not untranslated else '미완성',source_messages=len(rows),translated_messages=len(mapping),preserved_messages=len(preserved),untranslated_messages=len(untranslated),errors=errors,complete=not errors and not untranslated)
    (ROOT/'work/preserved_messages.json').write_text(json.dumps(preserved,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'work/untranslated_ids.json').write_text(json.dumps(untranslated,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'work/translation_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['complete'] else 2
if __name__=='__main__':sys.exit(main())
