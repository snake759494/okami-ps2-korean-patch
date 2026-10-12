import sys,json,struct
import numpy as np
from PIL import Image,ImageDraw
import afs,tex
ROOT='..'
idx=json.load(open(ROOT+'/work/menu_tex_index.json',encoding='utf-8'))
def raw_of(e):
    d=afs.read(e['k'],*afs.toc(e['k'])[0][e['i']][1:])
    tot=struct.unpack_from('<I',d,e['off']+16)[0];return d[e['off']:e['off']+16+tot]
if __name__=='__main__':
    sp=sys.argv[1];ids=[int(x) for x in sys.argv[2].split(',')];S=int(sys.argv[3]) if len(sys.argv)>3 else 4
    for n in ids:
        e=idx[n];t=tex.load(raw_of(e));im=Image.fromarray(tex.rgba(t),'RGBA')
        bg=Image.new('RGBA',im.size,(70,90,70,255));bg.alpha_composite(im)
        big=bg.resize((t['w']*S,t['h']*S),Image.NEAREST).convert('RGB');d=ImageDraw.Draw(big)
        for x in range(0,t['w'],8):d.line([(x*S,0),(x*S,4 if x%32 else 12)],fill=(255,0,0))
        for y in range(0,t['h'],8):d.line([(0,y*S),(4 if y%32 else 12,y*S)],fill=(255,0,0))
        big.save(f'{sp}/t{n}.png');print(n,e['file'],t['w'],t['h'],t['itype'],t['mode'])
