"""직접 번역한 메시지를 공통/지역 글꼴로 컴파일한다.

--check는 현재 번역의 문자 수용량과 글꼴 왕복 변환만 검사한다.
실제 배포 리소스는 미번역이 없어야 생성하며, 실행 검증을 대신하지 않는다.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,pickle,re,struct
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from fontTools.ttLib import TTFont
import afs,font,msd,pack,validate_translation,fixed_records
from build_iso import SOURCE_HASH

ROOT=Path(__file__).resolve().parents[1]
TOKEN=re.compile(r'(<[0-9A-F]{4}(?:,[0-9A-F]{4})*>)')
FONT=ROOT/'SeoulHangangB.ttf'
RASTER=ImageFont.truetype(str(FONT),22)
GLYPH_CACHE={}

def raster(c):
    if c in GLYPH_CACHE:return GLYPH_CACHE[c]
    im=Image.new('L',(26,26));draw=ImageDraw.Draw(im)
    if not c.isspace():
        l,t,r,b=draw.textbbox((0,0),c,font=RASTER)
        assert r-l<=26 and b-t<=26,(c,'글리프 셀 초과')
        # 세로 위치는 한글 '가' 기준선으로 고정(쉼표·마침표가 아래에 오도록)
        _,rt,_,rb=draw.textbbox((0,0),'가',font=RASTER)
        y=(26-(rb-rt))//2-rt
        assert y+t>=0 and y+b<=26,(c,'글리프 셀 초과')
        draw.text(((26-(r-l))//2-l,y),c,font=RASTER,fill=255)
    a=np.asarray(im)
    g=np.where(a>=192,1,np.where(a>=112,2,np.where(a>=40,3,0))).astype(np.uint8)
    ys,xs=np.nonzero(g)
    if len(xs):x0,y0,x1,y1=int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)
    else:x0,y0,x1,y1=0,0,8,1
    entry=struct.pack('<I',(x0<<8)|(y0<<14)|(x1<<20)|(y1<<26))
    GLYPH_CACHE[c]=(g,entry);return g,entry

def logical_glyph(pixels,i,w):
    j=i//2;x=j%(w//26)*26;y=j//(w//26)*26
    return (pixels[y:y+26,x:x+26]>>(2*(1-(i&1))))&3

def capacity(b):
    a=font.msa_parse(b['msa']);return (a['w']//26)*(a['h']//26)*2

def make_font(b,chars,templates,protected=()):
    old=font.msa_parse(b['msa'])
    if not chars and not protected:return b['msa'],b['mst'],{}
    n=len(protected)+len(chars);assert n<=722,(b['file'],n,'512x512 글꼴 용량 초과')
    if capacity(b)>=n:template=b
    else:template=min((x for x in templates if capacity(x)>=n),key=lambda x:len(x['mst']))
    hd=font.tim_hdr(template['mst']);w,h=hd['w'],hd['h']
    assert w<=512 and h<=512
    oh=font.tim_hdr(b['mst']);tail=b['mst'][oh['img']+oh['imsz']:]
    # 일부 PAC에는 글꼴 뒤에 다른 자료가 이어진다. 정체 불명의 자료는 이동시키지 않는다.
    assert len(tail)<=640 or (w,h)==(old['w'],old['h']),(b['file'],'불명 후행 데이터 재배치 필요')
    assert len(tail)>=640
    texture=template['mst'][:hd['img']+hd['imsz']]+tail
    pixels=np.zeros((h,w),np.uint8);entries=[]
    if protected:
        assert list(protected)==list(range(len(protected)))
        oldpixels=font.decode(b['mst'])
        for i in protected:
            font.put(pixels,i^1,logical_glyph(oldpixels,i,old['w']),26,26,w)
            entries.append(old['ent'][i])
    mapping={}
    for c in chars:
        i=len(entries);g,entry=raster(c);mapping[c]=i
        font.put(pixels,i^1,g,26,26,w);entries.append(entry)
    msa=font.msa_build(w,h,26,26,entries)
    swizzle=font.swizzled(template['mst'])
    mst=font.encode(texture,pixels,swz=swizzle)
    # 새 글꼴이 드문드문 배치되면 영상 거칠기 추정으로는 스위즐을 오판할 수 있다.
    # 원본 템플릿의 저장 방식을 유지하고 그 방식으로 역변환한다.
    decoded=font.decode(mst,swz=swizzle)
    assert np.array_equal(decoded,pixels),(b['file'],'텍스처 왕복 변환 실패')
    for c,i in mapping.items():assert np.array_equal(logical_glyph(decoded,i,w),raster(c)[0])
    assert mst[hd['img']+hd['imsz']:]==tail
    return msa,mst,mapping

def local_bank(b):
    banks=set()
    for message in msd.parse(b['msd']):
        if message is None:continue
        words=message[0];i=0
        while i<len(words):
            value=words[i]
            if value>=0x8000:i+=value&255
            else:
                if value>>12:banks.add(value>>12)
                i+=1
    assert len(banks)<=1,(b['file'],b['path'],banks)
    if banks:return banks.pop()
    if b['file']=='iteminfo':return 3
    if b['file']=='core.bin':return 0
    return 2

def encode_text(text,common,local,bank):
    out=[]
    for span in TOKEN.split(text):
        if not span:continue
        if TOKEN.fullmatch(span):out.extend(int(v,16) for v in span[1:-1].split(','))
        else:out.extend(common[c] if c in common else (bank<<12)|local[c] for c in span)
    assert out[-1]==msd.END
    return out

def make_msd(b,rows,texts,common,local):
    original=msd.parse(b['msd']);n=len(original);out=bytearray(4+8*n);out[:4]=b['msd'][:4]
    index={r['message']:r for r in rows};expected=[]
    for i,item in enumerate(original):
        if item is None:expected.append(None);continue
        row=index[i]
        if row['id'] in texts:
            words=encode_text(texts[row['id']],common,local,local_bank(b));ruby=None
            assert TOKEN.findall(row['source'])==TOKEN.findall(texts[row['id']])
        else:
            assert (b['file']=='core.bin' and i<7) or TOKEN.sub('',row['source'])==''
            words,ruby=item
        textoff=len(out);out.extend(struct.pack(f'<{len(words)}H',*words));rubyoff=0
        if ruby:
            rubyoff=len(out)
            for pos,base,kana in ruby:
                out.extend(struct.pack('<HHH',pos,base,len(kana)));out.extend(struct.pack(f'<{len(kana)}H',*kana))
            out.extend(b'\xff\xff')
        struct.pack_into('<II',out,4+8*i,textoff,rubyoff);expected.append((words,ruby))
    out.extend(bytes((-len(out))%16));out=bytes(out)
    assert msd.parse(out)==expected,(b['file'],'메시지 왕복 변환 실패')
    return out

def rebuild(data,changes):
    record_changes={k:v for k,v in changes.items() if k[0]<0}
    if record_changes:
        assert len(record_changes)==len(changes),'고정 레코드와 일반 컨테이너 수정 혼합'
        candidates=[(name,stride,count) for name,(stride,count) in fixed_records.LAYOUT.items() if len(data)==stride*count]
        assert len(candidates)==1
        name,stride,count=candidates[0];records=fixed_records.split(name,data);out=bytearray(data)
        assert all(0<=-key[0]-1<count for key in changes),'존재하지 않는 고정 레코드'
        for record,chunk in records:
            sub={k[1:]:v for k,v in changes.items() if k[0]==-record-1}
            if not sub:continue
            patched=rebuild(chunk,sub)
            assert len(patched)<=stride,(name,record,len(patched),'고정 레코드 용량 초과')
            out[record*stride:(record+1)*stride]=patched.ljust(stride,b'\0')
        assert len(out)==len(data)
        for record,actual in fixed_records.split(name,bytes(out)):
            sub={k[1:]:v for k,v in changes.items() if k[0]==-record-1}
            if not sub:
                assert actual==records[record][1],(name,record,'미수정 레코드 변형')
            for path,wanted in sub.items():
                payload=actual
                for i in path:
                    _,start,end=pack.parse(payload)[i];payload=payload[start:end]
                assert payload.startswith(wanted) and not any(payload[len(wanted):]),(name,record,path,'고정 레코드 재추출 불일치')
        return bytes(out)
    parts=pack.parse(data);items=[data[a:z] for _,a,z in parts];branches=defaultdict(dict)
    for path,value in changes.items():
        if len(path)==1:items[path[0]]=value
        else:branches[path[0]][path[1:]]=value
    for i,sub in branches.items():items[i]=rebuild(items[i],sub)
    result=pack.build(items,[t for t,_,_ in parts])
    for path,wanted in changes.items():
        actual=result
        for i in path:
            _,a,z=pack.parse(actual)[i];actual=actual[a:z]
        assert actual==wanted,(path,'컨테이너 재추출 불일치')
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    validate_translation.main()
    validation=json.loads((ROOT/'work/translation_validation.json').read_text(encoding='utf-8'))
    assert not validation['errors']
    assert args.check or validation['complete'],'미번역이 남아 리소스 빌드를 중단합니다.'
    blocks=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes())
    rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
    texts={k:v for p in (ROOT/'translation').glob('*_ko.json') for k,v in json.loads(p.read_text(encoding='utf-8')).items()}
    byblock=defaultdict(list)
    for row in rows:byblock[row['block']].append(row)
    coreindex=next(i for i,b in enumerate(blocks) if b['file']=='core.bin');core=blocks[coreindex]
    protected=sorted({v&4095 for words,ruby in msd.parse(core['msd'])[:7] for v in words if v<32768})
    assert protected==list(range(248))
    frequency=Counter(TOKEN.sub('',''.join(texts.values())))
    required=set(TOKEN.sub('',''.join(texts[r['id']] for r in byblock[coreindex] if r['id'] in texts)))
    assert len(required)+len(protected)<=722
    shared=sorted(required)
    shared.extend(c for c,_ in frequency.most_common() if c not in required)
    shared=shared[:722-len(protected)]
    ttf=TTFont(FONT);available=ttf.getBestCmap();missing=sorted(c for c in frequency if ord(c) not in available)
    assert not missing,('선택 글꼴에 없는 문자',missing)
    templates=[b for b in blocks if len(b['mst'])>16 and len(b['mst'])-font.tim_hdr(b['mst'])['img']-font.tim_hdr(b['mst'])['imsz']==640]
    cm,ct,common=make_font(core,shared,templates,protected)
    resource_changes=defaultdict(dict);font_report=[];compiled_messages=0
    for bi,b in enumerate(blocks):
        br=byblock[bi];assigned=[r for r in br if r['id'] in texts]
        if not assigned:continue
        chars=sorted(set(TOKEN.sub('',''.join(texts[r['id']] for r in assigned)))-set(common))
        if bi==coreindex:msa,mst,local=cm,ct,{}
        else:msa,mst,local=make_font(b,chars,templates)
        a=font.msa_parse(msa)
        font_report.append(dict(file=b['file'],archive=b['archive'],index=b['index'],path=b['path'],record=b.get('record'),local_bank=local_bank(b),messages=len(assigned),local_glyphs=len(chars),texture=[a['w'],a['h']]))
        ready=all(r['id'] in texts or (b['file']=='core.bin' and r['message']<7) or TOKEN.sub('',r['source'])=='' for r in br)
        if args.check and not ready:continue
        newmsd=make_msd(b,br,texts,common,local)
        compiled_messages+=len(assigned)
        edits=resource_changes[b['archive'],b['index']]
        for slot,value in ((b['i_msd'],newmsd),(b['i_msa'],msa),(b['i_mst'],mst)):
            key=fixed_records.edit_path(b,slot);assert key not in edits;edits[key]=value
    report=dict(complete=validation['complete'] and not args.check,font=FONT.name,font_sha256=hashlib.sha256(FONT.read_bytes()).hexdigest(),source_sha256=SOURCE_HASH,common_glyphs=len(shared),original_catalog_glyphs_preserved=len(protected),font_roundtrip_verified=True,message_roundtrip_verified=compiled_messages,runtime_verified=False,blocks=font_report,files=[])
    if args.check:
        for (archive,index),changes in sorted(resource_changes.items()):
            name,offset,size=afs.toc(archive)[0][index]
            rebuild(afs.read(archive,offset,size),changes)
        report['containers_roundtrip_verified']=len(resource_changes)
    if not args.check:
        dest=ROOT/'work/build';dest.mkdir(exist_ok=True)
        for (archive,index),changes in sorted(resource_changes.items()):
            name,offset,size=afs.toc(archive)[0][index]
            payload=rebuild(afs.read(archive,offset,size),changes)
            path=dest/f'{archive}_{index:04d}.bin';path.write_bytes(payload)
            report['files'].append(dict(archive=archive,index=index,name=name,path=path.relative_to(ROOT).as_posix(),size=len(payload),sha256=hashlib.sha256(payload).hexdigest()))
        destination=dest/'manifest.json'
    else:destination=ROOT/'work/font_build_check.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('blocks','files')},ensure_ascii=False,indent=2))
    print(f'검증 글꼴 블록: {len(font_report)}')

if __name__=='__main__':main()
