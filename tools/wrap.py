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

def _wrap_page(body,limit,maxlines):
    lines=body.split('<A001>')
    if all(width(l)<=limit for l in lines):return body,False,False
    # 줄 앞뒤 공백 정리 후 공백으로 이어 붙여 단어 단위로 다시 채운다
    joined=' '.join(l.strip(' ') for l in lines if l.strip(' ')!='' or True).strip(' ')
    words=joined.split(' ')
    sp=width(' ')
    def fill(lim):
        out=[];cur='';cw=0
        for w in words:
            ww=width(w)
            if cur=='' :cur=w;cw=ww
            elif cw+sp+ww<=lim:cur+=' '+w;cw+=sp+ww
            else:out.append(cur);cur=w;cw=ww
        out.append(cur);return out
    new=fill(limit)
    over=len(new)>maxlines
    # 한 단어가 폭을 넘으면 글자 단위로 자른다
    fixed=[]
    for l in new:
        if width(l)<=limit:fixed.append(l);continue
        cur=''
        for span in TOKEN.split(l):
            if not span:continue
            if TOKEN.fullmatch(span):cur+=span;continue
            for c in span:
                if width(cur+c)>limit and width(cur)>0:fixed.append(cur);cur=''
                cur+=c
        fixed.append(cur)
    if len(fixed)>maxlines and SPLIT_OK[0]:
        # 대화창: 넘치는 줄은 다음 페이지로(입력 대기 + 지우기)
        chunks=['<A001>'.join(fixed[i:i+maxlines]) for i in range(0,len(fixed),maxlines)]
        still=any(width(l)>limit for l in fixed)
        return '<A301><A101>'.join(chunks),True,still
    still=any(width(l)>limit for l in fixed) or len(fixed)>maxlines
    return '<A001>'.join(fixed),True,still

def wrap(text,limit,maxlines):
    """반환: (새 텍스트, 바뀐 페이지 수, 여전히 넘치는 페이지 수)"""
    out='';changed=0;bad=0
    for body,term in _split_pages(text):
        nb,ch,st=_wrap_page(body,limit,maxlines)
        out+=nb+term;changed+=ch;bad+=st
    return out,changed,bad

def tokens_wo_newline(s):
    return [t for t in TOKEN.findall(s) if t not in LAYOUT_TOKENS]
