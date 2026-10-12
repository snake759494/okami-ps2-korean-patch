from pathlib import Path
import pickle,json
import numpy as np
from PIL import Image,ImageDraw
import font
ROOT=Path(__file__).resolve().parents[1]
B=pickle.loads((ROOT/'work/blocks.pkl').read_bytes())
R=json.loads((ROOT/'work/ocr.json').read_text(encoding='utf-8'))
tails={}
im=Image.new('L',(800,480),255);d=ImageDraw.Draw(im)
for bi,b in enumerate(B):
    a=font.msa_parse(b['msa']);n=a['n']
    if not n%2:continue
    img=font.decode(b['mst']);j=n//2;x=j%(a['w']//26)*26;y=j//(a['w']//26)*26
    g=(img[y:y+26,x:x+26]>>2)&3;k=g.tobytes().hex()
    R['refs'][bi].append(k);tails[str(bi)]=k
    q=len(tails)-1;xx=q%12*66;yy=q//12*80
    tile=np.where(g==1,0,np.where(g==2,77,np.where(g==3,140,255))).astype('uint8')
    im.paste(Image.fromarray(tile).resize((52,52)),(xx,yy));d.text((xx,yy+53),str(bi),fill=0)
(ROOT/'work/tail_glyphs.json').write_text(json.dumps(tails),encoding='utf-8')
im.save(ROOT/'work/tail_glyphs.png')
print('복원 대상',len(tails))
