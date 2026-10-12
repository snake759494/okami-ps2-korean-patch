from pathlib import Path
import pickle
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import font
ROOT=Path(__file__).resolve().parents[1]
B=pickle.loads((ROOT/'work/blocks.pkl').read_bytes())
G=font.glyphs(B[0]['msa'],B[0]['mst'])
fonts=sorted(ROOT.glob('*.ttf'))
im=Image.new('RGB',(1300,130+len(fonts)*95),'#f6f1e6');d=ImageDraw.Draw(im)
label=ImageFont.truetype(str(ROOT/'NanumSquareNeo-bRg.ttf'),19)
d.text((20,10),'원본 26×26 글리프와 작업 폴더 한글 폰트 비교',font=label,fill='black')
for j,i in enumerate(range(198,221)):
    a=G[i^1];a=np.where(a==1,255,np.where(a==2,178,np.where(a==3,115,0))).astype('uint8')
    tile=Image.new('RGB',(52,52),'#f6f1e6');tile.paste('black',(0,0,52,52),Image.fromarray(a).resize((52,52),Image.Resampling.NEAREST));im.paste(tile,(20+j*55,45))
for n,f in enumerate(fonts):
    y=130+n*95;d.text((20,y),f.name,font=label,fill='black')
    ft=ImageFont.truetype(str(f),22)
    tile=Image.new('RGB',(450,35),'#f6f1e6');ImageDraw.Draw(tile).text((0,-1),'태양의 여신 아마테라스 붓놀림으로 세상을 구하다',font=ft,fill='black')
    im.paste(tile.resize((900,70),Image.Resampling.NEAREST),(360,y-3))
out=ROOT/'work/font_comparison.png';im.save(out);print(out)
sheet=Image.new('L',(16*52,13*68),255);sd=ImageDraw.Draw(sheet)
for i in range(198):
    a=G[i^1];a=np.where(a==1,0,np.where(a==2,77,np.where(a==3,140,255))).astype('uint8')
    x=(i%16)*52;y=(i//16)*68;sheet.paste(Image.fromarray(a).resize((52,52)),(x,y));sd.text((x,y+51),str(i),fill=0)
sheet.save(ROOT/'work/common_glyphs.png')
