import sys,json,pickle,numpy as np
sys.path.insert(0,'tools'); import font
from PIL import Image, ImageDraw, ImageFont
sp=sys.argv[1]
R=json.load(open('work/ocr.json',encoding='utf-8')); B=pickle.load(open('work/blocks.pkl','rb'))
ci=[i for i,b in enumerate(B) if b['file']=='core.bin'][0]
order=[]; seen=set()
for i,k in enumerate(R['refs'][ci]):
    if i>=198 and k not in seen: seen.add(k); order.append(k)
for bi,r in enumerate(R['refs']):
    for k in r:
        if k not in seen: seen.add(k); order.append(k)
print(len(order))
json.dump(order,open('work/kanji_order.json','w'))
lab=ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf',14)
per=200
for s in range(0,len(order),per):
    ks=order[s:s+per]; rows=(len(ks)+19)//20
    im=Image.new('L',(40+20*56,rows*60),0); d=ImageDraw.Draw(im)
    for j,k in enumerate(ks):
        g=np.frombuffer(bytes.fromhex(k),np.uint8).reshape(26,26)
        a=np.where(g==0,0,np.where(g==1,255,np.where(g==2,190,120))).astype(np.uint8)
        t=Image.fromarray(a).resize((52,52),Image.NEAREST)
        y,x=divmod(j,20); im.paste(t,(40+x*56,y*60+4))
    for y in range(rows): d.text((2,y*60+20),str(y),fill=255,font=lab)
    im.save(sp+'/kj_%02d.png'%(s//per))
