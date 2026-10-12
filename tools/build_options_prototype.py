"""설정 화면 한글 리소스 시제품. ISO 완성 빌드가 아니며 실행 검증이 필요하다."""
from pathlib import Path
import json,pickle,struct,re,hashlib
import numpy as np
from PIL import Image,ImageFont,ImageDraw
import font,msd,pack,afs
ROOT=Path(__file__).resolve().parents[1]
def main():
    B=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes())
    b=next(x for x in B if x['archive']==0 and x['index']==804)
    texts=json.loads((ROOT/'translation/options_ko.json').read_text(encoding='utf-8'))
    rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
    src={r['id']:r for r in rows}
    rx=re.compile(r'<[0-9A-F]{4}(?:,[0-9A-F]{4})*>')
    chars=sorted(set(''.join(rx.sub('',s) for s in texts.values())))
    candidates=[]
    for item in B:
        a=font.msa_parse(item['msa'])
        if a['cw']==26 and a['ch']==26 and (a['w']//26)*(a['h']//26)*2>=len(chars):
            candidates.append((a['w']*a['h'],item))
    template=min(candidates,key=lambda x:x[0])[1]
    hd=font.tim_hdr(template['mst']);w,h=hd['w'],hd['h']
    pixels=np.zeros((h,w),np.uint8);ent=[];glyphs=[]
    ft=ImageFont.truetype(str(ROOT/'SeoulHangangB.ttf'),22)
    for i,c in enumerate(chars):
        im=Image.new('L',(26,26));draw=ImageDraw.Draw(im)
        if c!=' ':
            l,t,r,bb=draw.textbbox((0,0),c,font=ft)
            draw.text(((26-(r-l))//2-l,(26-(bb-t))//2-t),c,font=ft,fill=255)
        a=np.asarray(im);g=np.where(a>=192,1,np.where(a>=112,2,np.where(a>=40,3,0))).astype(np.uint8)
        font.put(pixels,i^1,g,26,26,w);glyphs.append(g)
        ys,xs=np.nonzero(g)
        x0,y0,x1,y1=(int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)) if len(xs) else (0,0,8,1)
        assert max(x0,y0,x1,y1)<64
        ent.append(struct.pack('<I',(x0<<8)|(y0<<14)|(x1<<20)|(y1<<26)))
    # 같은 TIM3 치수의 원본 헤더를 사용한다. 팔레트는 설정 화면 원본과 대조한다.
    old_hd=font.tim_hdr(b['mst'])
    old_tail=b['mst'][old_hd['img']+old_hd['imsz']:]
    new_tail=template['mst'][hd['img']+hd['imsz']:]
    assert len(old_tail)==len(new_tail)==640,'팔레트 구조 불일치'
    tim_template=template['mst'][:hd['img']+hd['imsz']]+old_tail
    mst=font.encode(tim_template,pixels)
    assert mst[hd['img']+hd['imsz']:]==old_tail
    assert np.array_equal(font.decode(mst),pixels),'텍스처 역변환 실패'
    msa=font.msa_build(w,h,26,26,ent)
    cmap={c:0x2000+i for i,c in enumerate(chars)}
    original=msd.parse(b['msd']);new=bytearray(4+8*len(original));new[:4]=b['msd'][:4]
    expected=[]
    for mi in range(len(original)):
        key=f'0:0804:0.1:{mi:04d}';s=texts[key]
        assert rx.findall(src[key]['source'])==rx.findall(s),'제어 코드 변경'
        words=[]
        for tok in re.split('('+rx.pattern+')',s):
            if not tok:continue
            if tok.startswith('<'):words.extend(int(v,16) for v in tok[1:-1].split(','))
            else:words.extend(cmap[c] for c in tok)
        assert words[-1]==msd.END
        struct.pack_into('<II',new,4+mi*8,len(new),0)
        new.extend(struct.pack(f'<{len(words)}H',*words));expected.append(words)
    while len(new)%16:new.append(0)
    assert [r[0] for r in msd.parse(new)]==expected
    original_file=afs.read(b['archive'],b['offset'],b['size'])
    def rebuild(data,path):
        parts=pack.parse(data);items=[data[a:z] for _,a,z in parts]
        if path:items[path[0]]=rebuild(items[path[0]],path[1:])
        else:
            items[b['i_msd']]=bytes(new);items[b['i_msa']]=msa;items[b['i_mst']]=mst
        return pack.build(items,[t for t,_,_ in parts])
    payload=rebuild(original_file,b['path'])
    out=ROOT/'work/prototype';out.mkdir(exist_ok=True)
    (out/'idoption_ko.idd').write_bytes(payload)
    sheet=Image.new('L',(26*16,42*((len(chars)+15)//16)),255);draw=ImageDraw.Draw(sheet)
    for i,(c,g) in enumerate(zip(chars,glyphs)):
        a=np.where(g==1,0,np.where(g==2,77,np.where(g==3,140,255))).astype(np.uint8)
        x=i%16*26;y=i//16*42;sheet.paste(Image.fromarray(a),(x,y));draw.text((x,y+26),str(i),fill=0)
    sheet.save(out/'hangul_atlas.png')
    report=dict(prototype_only=True,runtime_verified=False,messages=len(texts),glyphs=len(chars),font='SeoulHangangB.ttf',texture=[w,h],original_size=len(original_file),prototype_size=len(payload),growth=len(payload)-len(original_file),texture_roundtrip=True,message_roundtrip=True,control_tokens_preserved=True,source_palette_preserved=True,sha256=hashlib.sha256(payload).hexdigest(),limitations=['MSA 글자 폭 메타데이터는 실행 검증 필요','확장 리소스의 AFS/FST 재배치 필요','전체 번역 미완성'])
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
