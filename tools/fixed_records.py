"""도감 PAC의 고정 크기 레코드. 오프셋/크기는 실행 시에도 유지한다."""
import struct
import pack

LAYOUT={'emfilemes.pac':(20480,71),'isfilemes.pac':(20480,30),
        'sgfudemes.pac':(12288,15),'skfilemes.pac':(20480,17)}

def split(name,data):
    if name not in LAYOUT:return [(None,data)]
    stride,count=LAYOUT[name]
    assert len(data)==stride*count,(name,len(data),stride,count)
    result=[]
    for i in range(count):
        chunk=data[i*stride:(i+1)*stride]
        assert pack.is_pack(chunk)
        assert [t for t,_,_ in pack.parse(chunk)]==['MSD','MSA','MST']
        result.append((i,chunk))
    return result

def trim_texture(texture):
    assert texture[:4]==b'TIM3'
    clsz,imsz=struct.unpack_from('<II',texture,20)
    hsz=struct.unpack_from('<H',texture,28)[0]
    end=16+hsz+imsz+clsz
    assert end<=len(texture) and not any(texture[end:]),'고정 레코드 뒤에 미분류 데이터가 있음'
    return texture[:end]

def edit_path(block,slot):
    prefix=() if 'record' not in block else (-block['record']-1,)
    return prefix+tuple(block['path'])+(slot,)
