"""AFS 번호/항목 번호를 영구 키로 사용하는 전체 원문 추출."""
from pathlib import Path
import json,pickle,collections,hashlib
import font,msd
ROOT=Path(__file__).resolve().parents[1]
def main():
    B=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes())
    labels=json.loads((ROOT/'work/glyph_labels.json').read_text(encoding='utf-8'))
    tables=[];missing={};cache={}
    for bi,b in enumerate(B):
        key=hashlib.sha256((b['msa'] or b'')+(b['mst'] or b'')).hexdigest()
        if key in cache:tables.append(cache[key]);continue
        a=font.msa_parse(b['msa']);n=a['n'];keys=[]
        if n:
            pixels=font.decode(b['mst']);cw=a['cw'];ch=a['ch'];cols=a['w']//cw
            for i in range(n):
                j=i//2;x=j%cols*cw;y=j//cols*ch
                g=(pixels[y:y+ch,x:x+cw]>>(2*(1-(i&1))))&3
                k=g.tobytes().hex();keys.append(k)
                if k not in labels:missing.setdefault(k,[]).append([bi,i])
        cache[key]=keys;tables.append(keys)
    core=next(i for i,b in enumerate(B) if b['file']=='core.bin')
    result=[];control_counts=collections.Counter();bounds=[]
    for bi,b in enumerate(B):
        for mi,m in enumerate(msd.parse(b['msd'])):
            if m is None:continue
            words,ruby=m;p=0;tokens=[];plain=[]
            while p<len(words):
                v=words[p]
                if v&0x8000:
                    n=v&255;assert n and p+n<=len(words)
                    tokens.append('<'+','.join(f'{w:04X}' for w in words[p:p+n])+'>')
                    control_counts[f'{v:04X}']+=1;p+=n
                    if v in (0xa001,0xa101,0xa301):plain.append('\n')
                else:
                    table=tables[bi if v&0x2000 else core];i=v&0xfff;p+=1
                    if i>=len(table):c=f'<범위초과:{v:04X}>';bounds.append([bi,mi,v])
                    else:c=labels.get(table[i],f'<미확인:{hashlib.sha256(bytes.fromhex(table[i])).hexdigest()[:12]}>')
                    tokens.append(c);plain.append(c)
            path='.'.join(str(v) for v in b['path']) or 'root'
            if b.get('record',0):path=f"record{b['record']}"+('' if path=='root' else '.'+path)
            result.append(dict(id=f"{b['archive']}:{b['index']:04d}:{path}:{mi:04d}",block=bi,message=mi,file=b['file'],source=''.join(tokens),readable=''.join(plain),translation=None))
    report=dict(archive_entries=3932,blocks=len(B),messages=len(result),unique_readable=len({r['readable'] for r in result}),characters=sum(len(r['readable']) for r in result),unidentified_glyphs=len(missing),out_of_bounds=bounds,commands=dict(control_counts),ocr_review_required=True,translation_complete=False)
    (ROOT/'translation/all_source_draft.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'work/all_extraction_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'work/unidentified_glyphs.json').write_text(json.dumps(missing),encoding='utf-8')
    (ROOT/'work/all_glyph_refs.json').write_text(json.dumps(tables),encoding='utf-8')
    print(json.dumps({**report,'commands':len(control_counts)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
