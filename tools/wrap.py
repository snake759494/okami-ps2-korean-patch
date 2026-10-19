"""빌드 시 자동 줄바꿈: 원본 창 폭(블록 안 일본어 최대 줄 폭)을 넘는 페이지만 단어 단위로 다시 나눈다.
번역 파일은 바꾸지 않는다. 줄바꿈 토큰 <A001> 외의 제어 토큰은 순서·위치(단어에 붙어서) 그대로 유지한다."""
import struct
from build_resources import TOKEN,raster
import msd
GAP=2
PAGE={'A301','A101','8001'}
SPLIT_OK=[False]
LAYOUT_TOKENS={'<A001>','<A301>','<A101>'}

def ew(e):
    v=struct.unpack('<I',e)[0];return ((v>>20)&63)-((v>>8)&63)+GAP

def width(s,adv=None):
    w=0
    for span in TOKEN.split(s):
        if not span or TOKEN.fullmatch(span):continue
        for c in span:w+=ew(raster(c)[1])
    return w

def jp_layout(words,entry):
    """원문 메시지의 (최대 줄 폭, 페이지당 최대 줄 수)."""
    maxw=0;maxl=1;cur=0;lines=1;i=0
    while i<len(words):
        v=words[i]
        if v>=0x8000:
            if v==0xA001:maxw=max(maxw,cur);cur=0;lines+=1
            elif v in (0xA301,0xA101,0x8001):
                maxw=max(maxw,cur);cur=0;maxl=max(maxl,lines if v!=0xA301 else lines);
                if v in (0xA101,0x8001) or True:lines=1
            i+=v&255;continue
        cur+=entry(v);i+=1
    return maxw,maxl

def _split_pages(text):
    """[(page_body, terminator_token_or_empty)] — body 안에는 <A001> 포함."""
    out=[];cur=''
    for span in TOKEN.split(text):
        if not span:continue
        if TOKEN.fullmatch(span) and span[1:5] in PAGE and len(span)==6:
            out.append((cur,span));cur=''
        else:cur+=span
    if cur:out.append((cur,''))
    return out

def _fill(words,lim):
    sp=width(' ');out=[];cur='';cw=0
    for w in words:
        ww=width(w)
        if cur=='':cur=w;cw=ww
        elif cw+sp+ww<=lim:cur+=' '+w;cw+=sp+ww
        else:out.append(cur);cur=w;cw=ww
    out.append(cur);return out

def _wrap_page(body,limit,maxlines,split_ok,cap):
    lines=body.split('<A001>')
    if len(lines)<=maxlines and all(width(l)<=limit for l in lines):return body,False,False
    words=' '.join(l.strip(' ') for l in lines).strip(' ').split(' ')
    new=_fill(words,limit)
    if len(new)>maxlines:
        # 원문 줄 수 안에 들도록 폭을 cap 까지 넓혀 본다(창 줄 수를 넘기지 않는 것이 우선)
        lim=limit
        while len(new)>maxlines and lim<cap:
            lim=min(cap,lim+4);new=_fill(words,lim)
    if len(new)>maxlines and split_ok:
        chunks=['<A001>'.join(new[i:i+maxlines]) for i in range(0,len(new),maxlines)]
        return '<A301><A101>'.join(chunks),True,False
    return '<A001>'.join(new),True,len(new)>maxlines

def wrap(text,limit,maxlines,split_ok=None,cap=None):
    """반환: (새 텍스트, 바뀐 페이지 수, 여전히 넘치는 페이지 수)"""
    if split_ok is None:split_ok=SPLIT_OK[0]
    if cap is None:cap=limit
    out='';changed=0;bad=0
    for body,term in _split_pages(text):
        nb,ch,st=_wrap_page(body,limit,maxlines,split_ok,cap)
        out+=nb+term;changed+=ch;bad+=st
    return out,changed,bad

def tokens_wo_newline(s):
    return [t for t in TOKEN.findall(s) if t not in LAYOUT_TOKENS]
