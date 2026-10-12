"""원본 메시지를 글리프 픽셀로 렌더링하여 OCR을 검토한다."""
from pathlib import Path
import json,pickle,sys
import numpy as np
from PIL import Image,ImageDraw
import font,msd
ROOT=Path(__file__).resolve().parents[1]
B=pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes());core=next(b for b in B if b['file']=='core.bin')
def glyphs(b):
    a=font.msa_parse(b['msa']);out=[]
    if not a['n']:return out
    pixels=font.decode(b['mst']);cols=a['w']//26
    for i in range(a['n']):
        j=i//2;x=j%cols*26;y=j//cols*26
        g=(pixels[y:y+26,x:x+26]>>(2*(1-(i&1))))&3
        out.append(Image.fromarray(np.where(g==1,0,np.where(g==2,77,np.where(g==3,140,255))).astype(np.uint8)))
    return out
cg=glyphs(core);tiles=[]
for spec in sys.argv[1:]:
    index,start,end=map(int,spec.split(':'));b=next(x for x in B if x['archive']==0 and x['index']==index);local=glyphs(b);msgs=msd.parse(b['msd'])
    for mi in range(start,end):
        if not msgs[mi]:continue
        words=msgs[mi][0];p=0;images=[]
        while p<len(words):
            v=words[p]
            if v>=32768:p+=v&255;continue
            images.append((local if v&8192 else cg)[v&4095]);p+=1
        for offset in range(0,max(1,len(images)),30):
            im=Image.new('L',(900,36),255);d=ImageDraw.Draw(im);d.text((0,10),f'{index}:{mi}' if not offset else f'+{offset}',fill=0)
            for j,g in enumerate(images[offset:offset+30]):im.paste(g,(90+j*26,0))
            tiles.append(im)
out=Image.new('L',(900,36*len(tiles)),255)
for i,t in enumerate(tiles):out.paste(t,(0,i*36))
dest=ROOT/'work/source_review.png';out.save(dest);print(dest)
