"""메시지 글꼴: MSA(글자 정보) + MST(TIM3, 4bpp 2비트x2겹, PSMCT32 업로드 스위즐)."""
import struct, numpy as np
import gsmem

def msa_parse(b):
    n, w, h, cw, ch = struct.unpack_from('<HHHBB', b, 0)
    ent = [b[8+4*i:12+4*i] for i in range(n)]
    return dict(n=n, w=w, h=h, cw=cw, ch=ch, ent=ent)

def msa_build(w, h, cw, ch, ent, size=None):
    out = bytearray(struct.pack('<HHHBB', len(ent), w, h, cw, ch))
    for e in ent: out += e
    while len(out) % 16: out.append(0)
    if size is not None:
        assert len(out) <= size; out += bytes(size - len(out))
    return bytes(out)

def tim_hdr(t):
    tot, clsz, imsz, hsz, clc, fmt, mip, ctype, itype, w, h = struct.unpack_from('<IIIHHBBBBHH', t, 16)
    return dict(tot=tot, clsz=clsz, imsz=imsz, hsz=hsz, clc=clc, ctype=ctype, itype=itype, w=w, h=h, img=16+hsz)

_cache = {}
def _map(w, h):
    """PSMT4 (w,h) 픽셀 -> 선형 버퍼의 니블 주소 (PSMCT32 w/2 x h/4 업로드)."""
    key = (w, h)
    if key in _cache: return _cache[key]
    w32, h32 = w // 2, h // 4
    bw32 = max(1, w32 // 64)
    # 32비트 업로드: 선형 i 번째 워드 -> GS 주소
    i32 = gsmem.index32(0, bw32, w32, h32).reshape(-1)  # 각 선형 워드의 바이트 주소
    inv = {}
    lin = np.full(max(i32.max() + 4, 1) , -1, np.int64)
    lin[i32] = np.arange(len(i32)) * 4
    bw4 = max(2, w // 64)
    a = np.array([[gsmem.addr4(0, bw4, x, y) for x in range(w)] for y in range(h)], np.int64)
    byte = a >> 1
    word_gs = byte & ~3
    lb = lin[word_gs] + (byte & 3)
    m = lb * 2 + (a & 1)
    _cache[key] = m
    return m

def _rough(a):
    a = (a > 0).astype(np.int16)
    return int(np.abs(np.diff(a, axis=0)).sum() + np.abs(np.diff(a, axis=1)).sum())

def swizzled(t):
    """텍스처가 스위즐(PSMCT32 업로드)인지 판정 — 작은 텍스처는 선형."""
    hd = tim_hdr(t); w, h = hd['w'], hd['h']
    raw = np.frombuffer(t[hd['img']:hd['img'] + w*h//2], np.uint8)
    nib = np.empty(w*h, np.uint8); nib[0::2] = raw & 15; nib[1::2] = raw >> 4
    if not nib.any(): return w >= 512
    return _rough(nib[_map(w, h)]) < _rough(nib.reshape(h, w))

def decode(t, swz=None):
    """TIM3 -> (h,w) 4bit 인덱스 배열."""
    hd = tim_hdr(t)
    w, h = hd['w'], hd['h']
    raw = np.frombuffer(t[hd['img']:hd['img'] + w*h//2], np.uint8)
    nib = np.empty(w*h, np.uint8); nib[0::2] = raw & 15; nib[1::2] = raw >> 4
    if swz is None: swz = swizzled(t)
    if not swz: return nib.reshape(h, w)
    return nib[_map(w, h)]

def encode(t, img, swz=None):
    hd = tim_hdr(t); w, h = hd['w'], hd['h']
    if swz is None: swz = swizzled(t)
    m = _map(w, h).reshape(-1) if swz else np.arange(w*h)
    nib = np.zeros(w*h, np.uint8); nib[m] = img.reshape(-1)
    raw = (nib[0::2] | (nib[1::2] << 4)).astype(np.uint8).tobytes()
    out = bytearray(t); out[hd['img']:hd['img'] + len(raw)] = raw
    return bytes(out)

def glyphs(msa, t):
    """글리프 i -> (ch,cw) 0..3 배열."""
    a = msa_parse(msa); img = decode(t)
    cw, ch = a['cw'], a['ch']; cols = a['w'] // cw
    out = []
    for i in range(a['n']):
        j = i // 2; x = (j % cols) * cw; y = (j // cols) * ch
        g = (img[y:y+ch, x:x+cw] >> (2 * (i & 1))) & 3
        out.append(g)
    return out

def put(img, i, g, cw, ch, w):
    cols = w // cw; j = i // 2; x = (j % cols) * cw; y = (j // cols) * ch
    sh = 2 * (i & 1); mask = np.uint8(~(3 << sh) & 15)
    img[y:y+ch, x:x+cw] = (img[y:y+ch, x:x+cw] & mask) | (g.astype(np.uint8) << sh)
