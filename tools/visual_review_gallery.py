"""원본 메뉴 텍스처를 검수용으로만 렌더링한다. 게임 데이터를 수정하지 않는다."""
import json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw
import afs,tim2,font,gsmem
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'work/visual_review'

def decode_candidates(data,g):
    im,idx,cl=tim2.to_image(data,g)
    mode='linear'
    if idx is not None and g['w']>=128 and g['h']>=64:
        w,h=g['w'],g['h'];original=np.frombuffer(idx,np.uint8).reshape(h,w)
        if g['itype']==4:
            candidate=font.decode(data,swz=True)
        else:
            w32,h32=w//2,h//2
            addresses=gsmem.index32(0,max(1,w32//64),w32,h32).reshape(-1)
            inv=np.full(int(addresses.max())+4,-1,np.int64)
            for k in range(4):inv[addresses+k]=np.arange(len(addresses))*4+k
            texture_addresses=np.array([[gsmem.addr8(0,max(2,w//64),x,y) for x in range(w)] for y in range(h)])
            mapping=inv[texture_addresses]
            assert mapping.min()>=0 and len(np.unique(mapping))==w*h
            candidate=np.frombuffer(idx,np.uint8)[mapping]
        palette=np.asarray([(r,gg,b,min(255,a*2)) for r,gg,b,a in cl],np.uint8)
        def rough(a):
            p=palette[a].astype(np.int32)
            return np.abs(np.diff(p,axis=0)).sum()+np.abs(np.diff(p,axis=1)).sum()
        if rough(candidate)<rough(original):
            im=Image.fromarray(palette[candidate]);mode='psmct32_upload_candidate'
    return im,mode

def main():
    DEST.mkdir(exist_ok=True)
    resources=json.loads((ROOT/'work/visual_resource_inventory.json').read_text(encoding='utf8'))['resources']
    selected=[r for r in resources if r['kind']=='texture' and r['file'].startswith('id')]
    entries=[];seen={};tiles=[]
    with open(afs.ISO,'rb') as source:
        for r in selected:
            source.seek(r['iso_offset']);raw=source.read(r['size']);digest=hashlib.sha256(raw).hexdigest()
            if digest in seen:
                entries.append(dict(id=r['id'],duplicate_of=seen[digest],source_sha256=digest));continue
            seen[digest]=r['id']
            # TIM3의 첫 picture 헤더는 TIM2와 같은 필드 구조다.
            data=b'TIM2'+raw[4:]
            try:
                pictures=tim2.parse(data)
                assert pictures
                for pi,g in enumerate(pictures):
                    assert 0<g['w']<=2048 and 0<g['h']<=2048
                    assert g['clut_off']+g['clut_size']<=len(data)
                    im,mode=decode_candidates(data,g)
                    filename=r['id'].replace(':','_')+f'_{pi}.png'
                    im.save(DEST/filename)
                    tile=Image.new('RGB',(320,210),'#aaa79c');d=ImageDraw.Draw(tile)
                    d.text((4,4),r['id']+f' [{pi}]',fill='black');d.text((4,19),r['file'],fill='black')
                    im.thumbnail((308,168));tile.paste(im,(6,39),im if im.mode=='RGBA' else None);tiles.append(tile)
                    entries.append(dict(id=r['id'],picture=pi,file=r['file'],image=filename,width=g['w'],height=g['h'],source_sha256=digest,review_status='pending',decode_mode=mode))
            except (AssertionError,ValueError,IndexError,TypeError) as e:
                entries.append(dict(id=r['id'],error=str(e),review_status='decode_failed'))
    for start in range(0,len(tiles),20):
        page=Image.new('RGB',(1280,1050),'white')
        for j,tile in enumerate(tiles[start:start+20]):page.paste(tile,((j%4)*320,(j//4)*210))
        page.save(DEST/f'menu_{start//20:02d}.png')
    (DEST/'manifest.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(resources=len(selected),unique_payloads=len(seen),pictures=len(tiles),pages=(len(tiles)+19)//20),ensure_ascii=False))

if __name__=='__main__':main()
