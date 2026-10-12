"""UI 텍스처(TIM2/TIM3) 픽셀 읽기·쓰기 — 크기·팔레트는 그대로, 인덱스만 교체한다.
4bpp(128x64 이상): PSMCT32 업로드 스위즐, 8bpp(128x64 이상): PSMCT32 업로드 스위즐(PSMT8), 그 밖은 선형.
실제 저장 방식은 원본에서 거칠기가 작은 쪽으로 판정한다(visual_review_gallery 와 같은 기준)."""
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tim2, font, gsmem

_map8 = {}
def map8(w, h):
    if (w, h) in _map8: return _map8[w, h]
    w32, h32 = w // 2, h // 2
    addresses = gsmem.index32(0, max(1, w32 // 64), w32, h32).reshape(-1)
    inv = np.full(int(addresses.max()) + 4, -1, np.int64)
    for k in range(4): inv[addresses + k] = np.arange(len(addresses)) * 4 + k
    ta = np.array([[gsmem.addr8(0, max(2, w // 64), x, y) for x in range(w)] for y in range(h)])
    m = inv[ta]; assert m.min() >= 0 and len(np.unique(m)) == w * h
    _map8[w, h] = m; return m

def load(raw):
    data = b'TIM2' + raw[4:]
    g = tim2.parse(data)[0]
    cl = tim2.clut_rgba(data, g)
    pal = np.asarray(cl, np.int32)
    w, h, t = g['w'], g['h'], g['itype']
    o = g['img_off']
    if t == 4:
        rawb = np.frombuffer(data[o:o + w * h // 2], np.uint8)
        lin = np.empty(w * h, np.uint8); lin[0::2] = rawb & 15; lin[1::2] = rawb >> 4
        lin = lin.reshape(h, w); sw = None
        if w >= 128 and h >= 64:
            sw = font.decode(raw, swz=True)
    elif t == 5:
        lin = np.frombuffer(data[o:o + w * h], np.uint8).reshape(h, w); sw = None
        if w >= 128 and h >= 64:
            sw = np.frombuffer(data[o:o + w * h], np.uint8)[map8(w, h)]
    else:
        raise ValueError('지원하지 않는 형식 %d' % t)
    mode = 'linear'; idx = lin
    if sw is not None:
        def rough(a):
            p = pal[a]
            return np.abs(np.diff(p, axis=0)).sum() + np.abs(np.diff(p, axis=1)).sum()
        if rough(sw) < rough(lin): idx = sw; mode = 'swz'
    return dict(g=g, pal=pal, idx=idx.copy(), mode=mode, w=w, h=h, itype=t)

def save(raw, tx):
    data = bytearray(raw)
    g = tx['g']; w, h = tx['w'], tx['h']; o = g['img_off']; idx = tx['idx'].astype(np.uint8)
    if tx['itype'] == 4:
        if tx['mode'] == 'swz':
            out = font.encode(bytes(raw), idx, swz=True)
            assert np.array_equal(font.decode(out, swz=True), idx)
            return out
        lin = idx.reshape(-1)
        data[o:o + w * h // 2] = (lin[0::2] | (lin[1::2] << 4)).astype(np.uint8).tobytes()
    else:
        if tx['mode'] == 'swz':
            buf = np.zeros(w * h, np.uint8); buf[map8(w, h)] = idx; data[o:o + w * h] = buf.tobytes()
        else:
            data[o:o + w * h] = idx.tobytes()
    out = bytes(data)
    chk = load(out)
    assert np.array_equal(chk['idx'], idx) or tx['mode'] == 'linear', '왕복 실패'
    return out

def rgba(tx):
    p = tx['pal'][tx['idx']].astype(np.int32)
    p[..., 3] = np.minimum(255, p[..., 3] * 2)
    return p.astype(np.uint8)

def nearest(pal, rgba_target):
    """팔레트에서 RGBA(알파 0..128) 가장 가까운 인덱스."""
    d = ((pal - np.asarray(rgba_target, np.int32)) ** 2 * np.array([1, 1, 1, 4])).sum(1)
    return int(d.argmin())
