"""미완성 검증용 ISO. 번역이 끝난 블록만 한글로 넣는다.
공용 글꼴(core.bin)은 남은 일본어 대사가 참조하는 칸을 그대로 두고, 참조되지 않는 칸에만
자주 쓰는 한글 음절을 배치해 지역 글꼴(특히 고정 크기 도감 PAC 레코드)의 부담을 줄인다."""
import json,pickle
from collections import defaultdict,Counter
import numpy as np
import afs,font,msd,validate_translation,fixed_records,wrap
import pack,struct
from PIL import Image,ImageDraw,ImageFont
from build_resources import ROOT,TOKEN,make_font,make_msd,rebuild,raster,FONT,TTFont,local_bank,logical_glyph,capacity,encode_text

SMALL_CACHE={}
def raster_small(c,cell):
    """cell×cell 칸용 글리프 (26칸 기준 22px 글자를 비례 축소)."""
    key=(c,cell)
    if key in SMALL_CACHE:return SMALL_CACHE[key]
    f=ImageFont.truetype(str(FONT),round(22*cell/26))
    im=Image.new('L',(cell,cell));d=ImageDraw.Draw(im)
    if not c.isspace():
        l,t,r,b=d.textbbox((0,0),c,font=f);assert r-l<=cell and b-t<=cell,(c,cell)
        _,rt,_,rb=d.textbbox((0,0),'가',font=f);y=(cell-(rb-rt))//2-rt
        y=max(-t,min(y,cell-b))
        d.text(((cell-(r-l))//2-l,y),c,font=f,fill=255)
    a=np.asarray(im);g=np.where(a>=192,1,np.where(a>=112,2,np.where(a>=40,3,0))).astype(np.uint8)
    ys,xs=np.nonzero(g)
    x0,y0,x1,y1=(int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)) if len(xs) else (0,0,cell//3,1)
    SMALL_CACHE[key]=(g,struct.pack('<I',(x0<<8)|(y0<<14)|(x1<<20)|(y1<<26)));return SMALL_CACHE[key]

def make_font_small(b,chars,template,cell):
    """고정 레코드용: 256x128 텍스처에 작은 칸으로 배치."""
    hd=font.tim_hdr(template['mst']);w,h=hd['w'],hd['h']
    oh=font.tim_hdr(b['mst']);tail=b['mst'][oh['img']+oh['imsz']:];assert len(tail)>=640
    texture=template['mst'][:hd['img']+hd['imsz']]+tail
    pixels=np.zeros((h,w),np.uint8);entries=[];mapping={}
    assert (w//cell)*(h//cell)*2>=len(chars)
    for c in chars:
        i=len(entries);g,e=raster_small(c,cell);mapping[c]=i
        font.put(pixels,i^1,g,cell,cell,w);entries.append(e)
    msa=font.msa_build(w,h,cell,cell,entries)
    swz=font.swizzled(template['mst']);mst=font.encode(texture,pixels,swz=swz)
    assert np.array_equal(font.decode(mst,swz=swz),pixels)
    return msa,mst,mapping

def record_fit(b,msdb,msa,mst):
    stride=fixed_records.LAYOUT[b['file']][0]
    return len(pack.build([msdb,msa,mst],['MSD','MSA','MST']))<=stride
from build_iso import build

def core_codes(b):
    """블록 MSD 가 참조하는 공용(뱅크 0) 글리프 번호."""
    used=set()
    for item in msd.parse(b['msd']):
        if item is None:continue
        words=item[0];i=0
        while i<len(words):
            v=words[i]
            if v>=0x8000:i+=v&255;continue
            if v>>12==0:used.add(v)
            i+=1
    return used

def patch_core(core,mapping):
    """원본 공용 글꼴에서 mapping{문자:번호} 칸만 한글로 덮어쓴다."""
    a=font.msa_parse(core['msa']);swz=font.swizzled(core['mst'])
    pixels=font.decode(core['mst'],swz=swz).copy();ent=list(a['ent'])
    for c,k in mapping.items():
        g,entry=raster(c);font.put(pixels,k^1,g,26,26,a['w']);ent[k]=entry
    msa=font.msa_build(a['w'],a['h'],a['cw'],a['ch'],ent,size=len(core['msa']))
    mst=font.encode(core['mst'],pixels,swz=swz)
    assert len(mst)==len(core['mst']) and np.array_equal(font.decode(mst,swz=swz),pixels)
    return msa,mst

def jp_codes(words):
    out=[];i=0
    while i<len(words):
        v=words[i]
        if v>=0x8000:i+=v&255;continue
        out.append(v);i+=1
    return out

def remap_words(words,remap):
    out=list(words);i=0
    while i<len(out):
        v=out[i]
        if v>=0x8000:i+=v&255;continue
        if v in remap:out[i]=remap[v]
        i+=1
    return out

def make_font_mixed(b,presets,chars,templates):
    """presets: [(26x26 글리프, MSA 항목)] 를 앞번호에, 이어서 한글 chars."""
    n=len(presets)+len(chars);assert n<=722,(b['file'],n,'512x512 글꼴 용량 초과')
    old=font.msa_parse(b['msa'])
    if capacity(b)>=n:template=b
    else:template=min((x for x in templates if capacity(x)>=n),key=lambda x:len(x['mst']))
    hd=font.tim_hdr(template['mst']);w,h=hd['w'],hd['h']
    oh=font.tim_hdr(b['mst']);tail=b['mst'][oh['img']+oh['imsz']:]
    assert len(tail)<=640 or (w,h)==(old['w'],old['h']),(b['file'],'불명 후행 데이터 재배치 필요')
    assert len(tail)>=640
    texture=template['mst'][:hd['img']+hd['imsz']]+tail
    pixels=np.zeros((h,w),np.uint8);entries=[];mapping={}
    for g,e in presets:
        font.put(pixels,len(entries)^1,g,26,26,w);entries.append(e)
    for c in chars:
        g,e=raster(c);mapping[c]=len(entries);font.put(pixels,len(entries)^1,g,26,26,w);entries.append(e)
    msa=font.msa_build(w,h,26,26,entries)
    swz=font.swizzled(template['mst']);mst=font.encode(texture,pixels,swz=swz)
    assert np.array_equal(font.decode(mst,swz=swz),pixels)
    return msa,mst,mapping

def make_msd_mixed(b,rows,texts,common,local,remap):
    """번역된 메시지는 한글로, 미번역 메시지는 글리프 번호만 remap 해 원문 유지(루비 포함)."""
    original=msd.parse(b['msd']);n=len(original);out=bytearray(4+8*n);out[:4]=b['msd'][:4]
    index={r['message']:r for r in rows};expected=[];bank=local_bank(b)
    for i,item in enumerate(original):
        if item is None:expected.append(None);continue
        row=index.get(i)
        if row is not None and row['id'] in texts:
            words=encode_text(texts[row['id']],common,local,bank);ruby=None
            assert wrap.tokens_wo_newline(row['source'])==wrap.tokens_wo_newline(texts[row['id']])
        else:
            words,ruby=item;words=remap_words(words,remap)
        textoff=len(out);out.extend(struct.pack(f'<{len(words)}H',*words));rubyoff=0
        if ruby:
            rubyoff=len(out)
            for pos,base,kana in ruby:
                out.extend(struct.pack('<HHH',pos,base,len(kana)));out.extend(struct.pack(f'<{len(kana)}H',*kana))
            out.extend(bytes([255,255]))
        struct.pack_into('<II',out,4+8*i,textoff,rubyoff);expected.append((words,ruby))
    out.extend(bytes((-len(out))%16));out=bytes(out)
    assert msd.parse(out)==expected,(b['file'],'메시지 왕복 변환 실패')
    return out

def main():
    validate_translation.main()
    state=json.loads((ROOT/'work/translation_validation.json').read_text(encoding='utf-8'))
    assert not state['errors']
    blocks=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes())
    rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
    texts={k:v for p in (ROOT/'translation').glob('*_ko.json') for k,v in json.loads(p.read_text(encoding='utf-8')).items()}
    byblock=defaultdict(list)
    for r in rows:byblock[r['block']].append(r)
    templates=[b for b in blocks if len(b['mst'])>16 and len(b['mst'])-font.tim_hdr(b['mst'])['img']-font.tim_hdr(b['mst'])['imsz']==640]
    cmap=TTFont(FONT).getBestCmap()
    ci=next(i for i,b in enumerate(blocks) if b['file']=='core.bin');core=blocks[ci]
    ca=font.msa_parse(core['msa']);ncore=ca['n'];cpix=font.decode(core['mst'])
    c2c=json.loads((ROOT/'work/core_code2ch.json').read_text(encoding='utf-8'))
    ch2code={v:int(k) for k,v in c2c.items()}
    SAME={'…':'…','!':'！','?':'？','「':'「','」':'」','(':'（',')':'）','·':'・','━':'━',**{str(d):chr(0xFF10+d) for d in range(10)}}
    PRESET={k:ch2code[v] for k,v in SAME.items() if v in ch2code}
    # 자동 줄바꿈: 블록 원문의 최대 줄 폭·페이지당 줄 수를 넘는 번역 페이지만 다시 나눔
    wrap_stats=Counter();still_over=[]
    for bi,b in enumerate(blocks):
        if not b['msd'] or len(b['mst'])<=16:continue
        le=font.msa_parse(b['msa'])['ent']
        ent=lambda v,le=le:wrap.ew(ca['ent'][v]) if v>>12==0 and v<len(ca['ent']) else (wrap.ew(le[v&4095]) if (v&4095)<len(le) else 24)
        M=msd.parse(b['msd'])
        laym={i:wrap.jp_layout(it[0],ent) for i,it in enumerate(M) if it}
        if not laym:continue
        limit=max(x[0] for x in laym.values())
        for r in byblock[bi]:
            if r['id'] not in texts or r['message'] not in laym:continue
            ml=laym[r['message']][1];sp=0xA101 in M[r['message']][0]
            t,ch,bad=wrap.wrap(texts[r['id']],limit,ml,sp,int(limit*1.35))
            if ch:wrap_stats['pages_rewrapped']+=ch;wrap_stats['messages']+=1;texts[r['id']]=t
            if bad:still_over.append(r['id'])
    print('자동 줄바꿈',dict(wrap_stats),'여전히 넘침',len(still_over),flush=True)
    PROTECT=248  # 공용 글리프 목록(가나·기호 등): 일본어 잔존 대사와 한글 대사가 함께 쓴다
    # 블록별: 번역 안 된 메시지의 원문 글자 번호 / 번역문 글자
    jp={};kor={}
    for bi,b in enumerate(blocks):
        if bi==ci or not b['msd'] or len(b['mst'])<=16:continue
        idx={r['message']:r for r in byblock[bi]};codes=set();ks=set()
        for i,item in enumerate(msd.parse(b['msd'])):
            if item is None:continue
            r=idx.get(i)
            if r is not None and r['id'] in texts:ks|=set(TOKEN.sub('',texts[r['id']]))
            else:codes|=set(jp_codes(item[0]))
        jp[bi]=codes;kor[bi]=ks
    core_kor=set()
    for r in byblock[ci]:
        if r['id'] in texts:core_kor|=set(TOKEN.sub('',texts[r['id']]))
    freq=Counter()
    for bi in kor:
        for c in kor[bi]:freq[c]+=1
    for c in core_kor:freq[c]+=1000
    order=sorted(freq,key=lambda c:(-freq[c],c))
    assert all(ord(c) in cmap for c in order)
    tables={k:afs.toc(k)[0] for k in (0,1)}
    frozen_log=[];jp_used={};core_catalog_keep=set()
    pins=set()     # 지역 글꼴에 다 못 옮겨 공용에 남겨 두는 일본어 글리프
    max_pins=None
    frozen=set()   # 재구성 실패로 원본 그대로 두는 블록
    max_pins=10**9  # 한도 없음(적용 메시지 최대)
    while True:
        jp_all=set()
        for bj in jp:jp_all|=jp_used.get(bj,jp[bj])
        used=({k for k in range(PROTECT) if k in jp_all}|set(PRESET.values())|core_catalog_keep)|pins
        for bi in frozen:used|={v for v in jp.get(bi,()) if v>>12==0}
        free=[k for k in range(ncore) if k not in used]
        common=dict(PRESET);common.update(zip([c for c in order if c not in PRESET],free))
        missing_core=core_kor-set(common)
        repin=False
        edits=defaultdict(dict);ids_by_file=defaultdict(list);skipped=[];failed=set();small_cells=[];partial=[]
        for bi in sorted(jp):
            if bi in frozen:continue
            b=blocks[bi];bank=local_bank(b)
            need_jp=sorted(v for v in jp[bi] if (v>>12) or v>=PROTECT)
            if not kor[bi] and not any(v>>12==0 for v in need_jp):continue   # 영향 없음
            la=font.msa_parse(b['msa'])
            lpix=None
            btexts={r['id']:texts[r['id']] for r in byblock[bi] if r['id'] in texts}
            orig=msd.parse(b['msd']);midx={r['message']:r for r in byblock[bi]}
            def plan_codes(bt):
                codes=set()
                for i,item in enumerate(orig):
                    if item is None:continue
                    r=midx.get(i)
                    if r is None or r['id'] not in bt:codes|=set(jp_codes(item[0]))
                return codes
            def plan(bt):
                codes=set()
                for i,item in enumerate(orig):
                    if item is None:continue
                    r=midx.get(i)
                    if r is None or r['id'] not in bt:codes|=set(jp_codes(item[0]))
                need=sorted(v for v in codes if (v>>12) or (v>=PROTECT and v not in pins))
                ks=set()
                for t in bt.values():ks|=set(TOKEN.sub('',t))
                return need,sorted(ks-set(common))
            need_jp,chars=plan(btexts)
            if len(need_jp)+len(chars)>722:
                # 먼저 일본어 잔존 대사의 공용 글리프를 공용 글꼴에 고정(번역문은 유지)
                cand=[v for v in need_jp if v>>12==0]
                over=len(need_jp)+len(chars)-722
                allowed=max_pins-len(pins)   # 공용 글꼴에 core 메뉴·이름 글자 자리를 남김
                base_need,_=plan({})
                necessary=max(0,len(base_need)-722)   # 번역을 다 되돌려도 넘치는 만큼은 반드시 고정
                if cand and (over<=min(allowed,len(cand)) or necessary>0):
                    k=over if over<=min(allowed,len(cand)) else min(len(cand),max(necessary,allowed))
                    pins.update(cand[:k]);repin=True;break
            while len(need_jp)+len(chars)>722 and btexts:
                # 그래도 모자라면 고유 글자를 가장 많이 늘리는 번역부터 원문으로 되돌림
                cnt=Counter(c for t in btexts.values() for c in set(TOKEN.sub('',t)) if c not in common)
                worst=max(btexts,key=lambda k:sum(1 for c in set(TOKEN.sub('',btexts[k])) if c not in common and cnt[c]==1))
                del btexts[worst];need_jp,chars=plan(btexts)
            if len(need_jp)+len(chars)>722:
                skipped.append(dict(archive=b['archive'],index=b['index'],file=b['file'],reason='지역 글꼴 수용량 초과'));failed.add(bi);continue
            jp_used[bi]={v for v in plan_codes(btexts) if v>>12==0}
            presets=[];remap={}
            if any(v>>12 for v in need_jp):lpix=font.decode(b['mst'])
            for v in need_jp:
                if v>>12==0:g=logical_glyph(cpix,v,ca['w']);e=ca['ent'][v]
                else:g=logical_glyph(lpix,v&4095,la['w']);e=la['ent'][v&4095]
                remap[v]=(bank<<12)|len(presets);presets.append((g,e))
            assigned=[r for r in byblock[bi] if r['id'] in btexts]
            if len(btexts)<sum(1 for r in byblock[bi] if r['id'] in texts):
                partial.append(dict(file=b['file'],index=b['index'],reverted=sum(1 for r in byblock[bi] if r['id'] in texts)-len(btexts)))
            try:
                if len(presets)+len(chars)>722:raise AssertionError('지역 글꼴 수용량 초과')
                msa,mst,local=make_font_mixed(b,presets,chars,templates)
                message=make_msd_mixed(b,byblock[bi],btexts,common,local,remap)
                if b['file'] in fixed_records.LAYOUT and not record_fit(b,message,msa,mst):
                    if presets:raise AssertionError('고정 레코드 용량 초과(일본어 잔존)')
                    sizes=[(256,128),(128,128),(256,64),(128,64)]
                    def _tries():
                        for tw,th in sizes:
                            tpl=next((x for x in templates if font.tim_hdr(x['mst'])['w']==tw and font.tim_hdr(x['mst'])['h']==th and font.swizzled(x['mst'])==(tw>=128 and th>=128)),None)
                            if tpl is None:continue
                            for cell in range(26,15,-1):
                                if (tw//cell)*(th//cell)*2>=len(chars):yield tpl,cell
                    for big,cell in _tries():
                        msa,mst,local=make_font_small(b,chars,big,cell)
                        message=make_msd_mixed(b,byblock[bi],btexts,common,local,remap)
                        if record_fit(b,message,msa,mst):small_cells.append((b['file'],fixed_records.edit_path(b,0)[0],cell,len(chars)));break
                    else:raise AssertionError('고정 레코드 용량 초과(작은 칸 포함)')
            except AssertionError as e:
                skipped.append(dict(archive=b['archive'],index=b['index'],file=b['file'],reason=str(e)));failed.add(bi);continue
            target=edits[b['archive'],b['index']]
            for slot,value in ((b['i_msd'],message),(b['i_msa'],msa),(b['i_mst'],mst)):
                key=fixed_records.edit_path(b,slot);assert key not in target;target[key]=value
            ids_by_file[b['archive'],b['index']].append((bi,[r['id'] for r in assigned]))
        payloads={}
        for (archive,index),changes in sorted(edits.items()):
            _,offset,size=tables[archive][index]
            try:payloads[archive,index]=rebuild(afs.read(archive,offset,size),changes)
            except AssertionError as e:
                skipped.append(dict(archive=archive,index=index,reason=str(e)))
                failed|={bi for bi,_ in ids_by_file[archive,index]}
        clash=set()
        for bj,cs in jp_used.items():
            if bj in frozen:continue
            clash|={v for v in cs if v<PROTECT and v not in used}
        if clash and not repin:
            core_catalog_keep|=clash;print('보호 칸 복원',len(clash),flush=True);continue
        if repin:
            print('공용 고정 글리프',len(pins),flush=True);continue
        if not failed:break
        print('재구성 실패 블록', len(failed), Counter(s['reason'][:30] for s in skipped), flush=True)
        frozen_log.extend(skipped);frozen|=failed
    # 공용 글꼴: 248번 이후 칸을 한글로, core.bin 대사는 번역문으로
    key=(core['archive'],core['index'])
    msa,mst=patch_core(core,{c:k for c,k in common.items() if c not in PRESET})
    core_texts={r['id']:texts[r['id']] for r in byblock[ci] if r['id'] in texts and not (set(TOKEN.sub('',texts[r['id']]))-set(common))}
    cmsd=make_msd_mixed(core,byblock[ci],core_texts,common,{},{})
    target=edits[key]
    for slot,value in ((core['i_msd'],cmsd),(core['i_msa'],msa),(core['i_mst'],mst)):
        target[fixed_records.edit_path(core,slot)]=value
    _,offset,size=tables[key[0]][key[1]]
    payloads[key]=rebuild(afs.read(key[0],offset,size),target)
    # TBL 안에 숨어 기존 추출에서 빠졌던 메시지 블록(17개): 원래 자리에서 같은 크기 이내로 교체
    mblocks=pickle.loads((ROOT/'work/missed_blocks.pkl').read_bytes())
    msrc=json.loads((ROOT/'translation/missed_source.json').read_text(encoding='utf-8'))
    mtx={}
    for f in sorted((ROOT/'translation').glob('*.mko.json')):mtx.update(json.loads(f.read_text(encoding='utf-8')))
    missed_report=[];applied_missed=[]
    def cur_data(k,i):
        if (k,i) in payloads:return payloads[k,i]
        return afs.read(k,*tables[k][i][1:])
    for mb in mblocks:
        pre='M:%d:%04d:%x:'%(mb['archive'],mb['index'],mb['pac_off'])
        mrows=[dict(r,message=int(r['id'].rsplit(':',1)[1])) for r in msrc if r['id'].startswith(pre)]
        btx={r['id']:mtx[r['id']] for r in mrows if r['id'] in mtx}
        lent=font.msa_parse(mb['msa'])['ent']
        ent2=lambda v,le=lent:wrap.ew(ca['ent'][v]) if v>>12==0 and v<len(ca['ent']) else (wrap.ew(le[v&4095]) if (v&4095)<len(le) else 24)
        MM=msd.parse(mb['msd'])
        laym={i:wrap.jp_layout(it[0],ent2) for i,it in enumerate(MM) if it}
        if laym:
            lim=max(x[0] for x in laym.values())
            for kk in list(btx):
                mi=int(kk.rsplit(':',1)[1])
                if mi not in laym:continue
                t2,chg,bad=wrap.wrap(btx[kk],lim,laym[mi][1],0xA101 in MM[mi][0],int(lim*1.35))
                if chg:btx[kk]=t2;wrap_stats['missed_rewrapped']+=1
        orig=msd.parse(mb['msd']);la=font.msa_parse(mb['msa'])
        codes=set()
        for r in mrows:
            if r['id'] in btx:continue
            item=orig[r['message']]
            if item:codes|=set(jp_codes(item[0]))
        need=sorted(v for v in codes if (v>>12) or v>=0)
        need=[v for v in need if not (v>>12==0 and v<0)]
        lpix=font.decode(mb['mst']) if la['n'] else None
        bank=local_bank(mb) if any(True for _ in [0]) else 3
        presets=[];remap={}
        for v in sorted(codes):
            if v>>12==0:
                if v in PRESET.values() and False:continue
                g=logical_glyph(cpix,v,ca['w']);e=ca['ent'][v]
            else:g=logical_glyph(lpix,v&4095,la['w']);e=la['ent'][v&4095]
            remap[v]=(bank<<12)|len(presets);presets.append((g,e))
        chars=sorted(set(TOKEN.sub('',''.join(btx.values())))-set(common))
        pac_size=mb['pac_end']-mb['pac_off']
        def assemble(msa,mst,local):
            md=make_msd_mixed(mb,mrows,btx,common,local,remap)
            items={'MSD':md,'MSA':msa,'MST':mst}
            return pack.build([items[t] for t in mb['tags']],mb['tags'])
        result=None;why=''
        try:
            msa,mst,local=make_font_mixed(mb,presets,chars,templates)
            out=assemble(msa,mst,local)
            if len(out)<=pac_size:result=out
            elif not presets:
                for tw,th in [(256,128),(128,128),(128,64),(64,64),(64,32),(32,32)]:
                    tpl=next((x for x in templates if font.tim_hdr(x['mst'])['w']==tw and font.tim_hdr(x['mst'])['h']==th),None)
                    if tpl is None:continue
                    for cell in range(26,11,-1):
                        if (tw//cell)*(th//cell)*2<len(chars):continue
                        msa,mst,local=make_font_small(mb,chars,tpl,cell);out=assemble(msa,mst,local)
                        if len(out)<=pac_size:result=out;break
                    if result:break
            if result is None:why='PAC 크기 초과 %d>%d'%(len(out),pac_size)
        except AssertionError as e:why=str(e)
        if result is None:
            missed_report.append(dict(file=mb['file'],index=mb['index'],status='보류',reason=why));continue
        k,i=mb['archive'],mb['index'];d=cur_data(k,i)
        origpac=afs.read(k,*tables[k][i][1:])[mb['pac_off']:mb['pac_end']]
        assert d.count(origpac)==1,(mb['file'],'원본 PAC 위치 불명')
        pos=d.find(origpac);payloads[k,i]=d[:pos]+result.ljust(pac_size,bytes(1))+d[pos+pac_size:]
        missed_report.append(dict(file=mb['file'],index=i,status='적용',translated=len(btx),messages=len(mrows),size=len(result),limit=pac_size))
        applied_missed.extend(btx)
    print('누락 블록',Counter(x['status'] for x in missed_report),[x for x in missed_report if x['status']!='적용'],flush=True)
    # UI 텍스처 라벨 교체(크기 불변, 같은 바이트의 중복 사본까지 전부)
    import relabel,hashlib
    spec=json.loads((ROOT/'translation/ui_labels.json').read_text(encoding='utf-8'))
    tindex=json.loads((ROOT/'work/menu_tex_index.json').read_text(encoding='utf-8'))
    oindex=json.loads((ROOT/'work/other_tex_index.json').read_text(encoding='utf-8'))
    scan=json.loads((ROOT/'work/tim_scan.json').read_text(encoding='utf-8'))
    filecache={}
    def fdata(k,i):
        if (k,i) in payloads:return payloads[k,i]
        if (k,i) not in filecache:filecache[k,i]=afs.read(k,*tables[k][i][1:])
        return filecache[k,i]
    tex_report=[]
    for n,labels in spec.items():
        if n.startswith('BOARD'):continue
        e=oindex[int(n[1:])] if n.startswith('X') else tindex[int(n)];d=fdata(e['k'],e['i'])
        if (e['k'],e['i']) in payloads:d=afs.read(e['k'],*tables[e['k']][e['i']][1:])
        tot=struct.unpack_from('<I',d,e['off']+16)[0];raw=d[e['off']:e['off']+16+tot]
        new=relabel.apply(raw,labels);assert len(new)==len(raw)
        hits=0
        for k,i,name,off,w,h,it in scan:
            if (w,h,it)!=(e['w'],e['h'],e['itype']):continue
            cur=fdata(k,i)
            if raw not in cur:continue
            c=cur.count(raw);payloads[k,i]=cur.replace(raw,new);hits+=c
        assert hits>=1,(n,'원본 텍스처를 찾지 못함')
        tex_report.append(dict(texture=n,file=e['file'],replaced=hits))
    # 미니게임 설명판(낚시 등): 상자 글을 다시 쓰고 같은 그림 사본 전부 교체
    for key,boxes in spec.get('BOARD',{}).items():
        fname,off=key.split(':');off=int(off)
        k,i=next((kk,ii) for kk in (0,1) for ii,(nm,_,_) in enumerate(tables[kk]) if nm==fname)
        d0=afs.read(k,*tables[k][i][1:]);tot=struct.unpack_from('<I',d0,off+16)[0];raw=d0[off:off+16+tot]
        new=relabel.apply_board(raw,boxes)
        if key in spec.get('BOARD_LABELS',{}):new=relabel.apply(new,spec['BOARD_LABELS'][key])
        assert len(new)==len(raw);hits=0
        for kk in (0,1):
            for ii,(nm,o,sz) in enumerate(tables[kk]):
                if sz>40_000_000:continue
                cur=fdata(kk,ii)
                if raw in cur:hits+=cur.count(raw);payloads[kk,ii]=cur.replace(raw,new)
        tex_report.append(dict(texture=key,replaced=hits))
    print('UI 텍스처 교체',len(tex_report),'종',sum(x['replaced'] for x in tex_report),'곳',flush=True)
    applied=[i for v in ids_by_file.values() for _,ids in v for i in ids]+list(core_texts)
    temp=ROOT/'work/preview_build';temp.mkdir(exist_ok=True)
    replacements={0:{},1:{}};generated=[]
    for (archive,index),payload in payloads.items():
        path=temp/f'{archive}_{index:04d}.bin';path.write_bytes(payload)
        replacements[archive][index]=path;generated.append(path)
    output=ROOT/'Ookami (Japan) (Korean).iso'
    print(f'빌드 시작: {len(applied)}개 메시지, {len(generated)}개 파일, 공용 한글 {len(common)}자, 공용 누락 {len(missing_core)}, 원본유지 블록 {len(frozen)}',flush=True)
    report=build(output,replacements)
    report.update(complete=False,preview_only=True,applied_messages=len(applied),applied_ids=applied,skipped=skipped+frozen_log,
                  frozen_blocks=len(frozen),missed_blocks=missed_report,applied_missed=len(applied_missed),ui_textures=tex_report,rewrap=dict(wrap_stats),rewrap_still_over=still_over,pinned_core_glyphs=len(pins),partial_blocks=partial,small_cell_records=small_cells,shared_hangul_in_core=len(common),
                  image_localization_complete=False,movie_subtitles=False,font=FONT.name)
    (ROOT/'work/preview_iso_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    output.with_suffix('.iso.sha256').write_text(report['sha256']+'  '+output.name+'\n',encoding='utf-8')
    (ROOT/'검증용_ISO_주의사항.txt').write_text(f'미완성 검증용 한글 ISO\n파일: {output.name}\n적용 메시지: {len(applied)}개\n미번역 대사는 일본어로 표시되며 일본어 이미지, 동영상 자막이 남아 있습니다.\n전체 한글패치 완성본이 아닙니다.\nSHA-256: {report["sha256"]}\n',encoding='utf-8')
    for path in generated:
        assert path.resolve().parent==temp.resolve();path.unlink()
    if not any(temp.iterdir()):temp.rmdir()
    print(json.dumps({k:v for k,v in report.items() if k not in ('applied_ids','skipped','small_cell_records')},ensure_ascii=False,indent=2),flush=True)
    print(Counter(s['reason'][:40] for s in report['skipped']))

if __name__=='__main__':main()
