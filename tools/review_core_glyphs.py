"""공통 글꼴 원본 판독용 시트. 글자 번호를 표시하고 픽셀을 그대로 확대한다."""
import pickle
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
import font
ROOT=Path(__file__).resolve().parents[1]
b=next(x for x in pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes()) if x['file']=='core.bin')
a=font.msa_parse(b['msa']);pixels=font.decode(b['mst'])
outdir=ROOT/'work/core_glyph_review';outdir.mkdir(exist_ok=True)
for start in range(0,a['n'],120):
    sheet=Image.new('L',(900,950),255);draw=ImageDraw.Draw(sheet)
    for i in range(start,min(a['n'],start+120)):
        j=i//2;x=j%(a['w']//26)*26;y=j//(a['w']//26)*26
        g=(pixels[y:y+26,x:x+26]>>(2*(1-(i&1))))&3
        tile=np.where(g==1,0,np.where(g==2,77,np.where(g==3,140,255))).astype(np.uint8)
        q=i-start;xx=q%12*75;yy=q//12*95
        sheet.paste(Image.fromarray(tile).resize((52,52)),(xx,yy));draw.text((xx,yy+56),str(i),fill=0)
    sheet.save(outdir/f'{start:03d}.png')
print(outdir)
