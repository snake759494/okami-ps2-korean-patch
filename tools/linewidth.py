"""줄 폭 전수 조사: 원문(원본 MSA 폭) 대비 번역문(서울한강체 래스터 폭)."""
import json,pickle,glob,re,struct
from collections import defaultdict
from build_resources import ROOT,TOKEN,raster
import msd,font
GAP=2
def ew(e):
    v=struct.unpack('<I',e)[0];return ((v>>20)&63)-((v>>8)&63)+GAP
def jp_lines(words,entry):
    lines=[];cur=0;i=0
    while i<len(words):
        v=words[i]
        if v>=0x8000:
            if v in (0xA001,0xA301,0xA101,0x8001):lines.append(cur);cur=0
            i+=v&255;continue
        cur+=entry(v);i+=1
    return [x for x in lines if x]
def ko_lines(text):
    out=[];cur=0
    for span in TOKEN.split(text):
        if not span:continue
        if TOKEN.fullmatch(span):
            if span[1:5] in ('A001','A301','A101','8001'):out.append(cur);cur=0
            continue
        for c in span:cur+=ew(raster(c)[1])
    return [x for x in out if x]
def main():
    blocks=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes())
    rows=json.loads((ROOT/'translation/all_source_draft.json').read_text(encoding='utf-8'))
    texts={k:v for p in glob.glob(str(ROOT/'translation/*_ko.json')) for k,v in json.load(open(p,encoding='utf-8')).items()}
    ci=next(i for i,b in enumerate(blocks) if b['file']=='core.bin');ce=font.msa_parse(blocks[ci]['msa'])['ent']
    by=defaultdict(list)
    for r in rows:by[r['block']].append(r)
    res=[]
    for bi,b in enumerate(blocks):
        if not b['msd'] or len(b['mst'])<=16:continue
        le=font.msa_parse(b['msa'])['ent']
        ent=lambda v:ew(ce[v]) if v>>12==0 and v<len(ce) else (ew(le[v&4095]) if (v&4095)<len(le) else 24)
        M=msd.parse(b['msd']);idx={r['message']:r for r in by[bi]}
        blockmax=0;items=[]
        for i,it in enumerate(M):
            if it is None:continue
            jl=jp_lines(it[0],ent);blockmax=max([blockmax]+jl)
            r=idx.get(i)
            if r and r['id'] in texts:items.append((r['id'],max(jl or [0]),ko_lines(texts[r['id']])))
        for rid,jm,kl in items:
            res.append(dict(id=rid,file=b['file'],jp_max=jm,block_max=blockmax,ko_max=max(kl or [0])))
    (ROOT/'work/linewidth.json').write_text(json.dumps(res,ensure_ascii=False),encoding='utf-8')
    return res
if __name__=='__main__':
    res=main()
    over=[r for r in res if r['ko_max']>r['block_max']]
    print(len(res),'블록 최대폭 초과',len(over))
    import collections;print(collections.Counter(r['file'] for r in over).most_common(15))
