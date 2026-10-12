"""원본 글리프 기반 원문 복원. OCR 초안은 반드시 직접 검토한다."""
from pathlib import Path
import json,pickle,collections,hashlib,sys
import numpy as np
import msd,font,afs,collect
ROOT=Path(__file__).resolve().parents[1]
def main():
    B=pickle.loads((ROOT/'work/blocks.pkl').read_bytes())
    R=json.loads((ROOT/'work/ocr.json').read_text(encoding='utf-8'))
    order=json.loads((ROOT/'work/kanji_order.json').read_text())
    labels={k: v[0][0] for k,v in R['res'].items()}
    tails=json.loads((ROOT/'work/tail_glyphs.json').read_text())
    tailchars='匹映初覧吹貯買状敏刮的壊部指塞憩航功別慮丹額額額奉程捧溢旬勇慎丈進元狂象訳慮恙協語怯就掛貸健健題題得休休史討'
    assert len(tails)==len(tailchars)
    for (bi,k),c in zip(tails.items(),tailchars):
        R['refs'][int(bi)].append(k);labels[k]=c
    for k in labels:
        if not any(bytes.fromhex(k)):labels[k]='　'
    for f in sorted((ROOT/'work/kj').glob('*.txt')):
        chars=''.join(f.read_text(encoding='utf-8-sig').split())
        for k,c in zip(order[int(f.stem)*200:],chars):labels[k]=c
    # 원본 숫자 글리프의 OCR 혼동 수정
    labels[R['refs'][0][20]]='６'
    kana='ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをん'
    kata='ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶ'
    assert len(kana)==83 and len(kata)==86
    for start,chars in ((25,kana),(108,kata)):
        for i,c in enumerate(chars,start):labels[R['refs'][0][i^1]]=c
    option='操作振機能音楽量効声設定初期終了常反転左右Ⅱ普非液状態更映'
    assert len(option)==29
    for i,c in enumerate(option):labels[R['refs'][5][i^1]]=c
    (ROOT/'work/glyph_labels.json').write_text(json.dumps(labels,ensure_ascii=False),encoding='utf-8')
    idx=afs.index();records=[]; controls=collections.Counter(); mismatches=[]; unknown=collections.Counter()
    for bi,b in enumerate(B):
        data=collect.sub(afs.read(*idx[b['file']]),b['path'])
        import pack
        parts=pack.parse(data)
        for name in ('msd','msa','mst'):
            i=b['i_'+name]
            if i is not None and data[parts[i][1]:parts[i][2]]!=b[name]:mismatches.append([bi,name])
        refs=R['refs'][bi]
        for mi,m in enumerate(msd.parse(b['msd'])):
            if m is None:continue
            words,ruby=m;chunks=[];p=0;plain=[]
            while p<len(words):
                v=words[p]
                if v>=0x8000:
                    n=v&255
                    assert n and p+n<=len(words),(bi,mi,p)
                    token='<'+','.join(f'{x:04X}' for x in words[p:p+n])+'>'
                    chunks.append(token);controls[f'{v:04X}']+=1;p+=n
                    if v in (0xa001,0xa101,0xa301):plain.append('\n')
                    continue
                p+=1
                use=refs if v&0x2000 else R['refs'][0]
                gi=(v&0xfff)^1
                if gi<len(use):c=labels[use[gi]]
                else:c=f'<G{v:04X}>';unknown[f'{bi}:{v:04X}']+=1
                chunks.append(c);plain.append(c)
            records.append(dict(id=f'{bi:03d}:{mi:04d}',file=b['file'],source=''.join(chunks),readable=''.join(plain),translation=None))
    out=ROOT/'translation';out.mkdir(exist_ok=True)
    report=dict(blocks=len(B),messages=len(records),source_cache_mismatches=mismatches,unknown_glyphs=dict(unknown),commands=dict(controls),ocr_review_required=True)
    (ROOT/'work/extraction_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({**report,'unknown_glyphs':len(unknown),'commands':len(controls)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
