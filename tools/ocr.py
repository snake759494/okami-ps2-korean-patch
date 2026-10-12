"""원본 글리프 식별(템플릿 매칭) — 원문 추출용. 결과: work/jp_glyphs.json"""
import sys, os, json, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FONTS = [r'C:\Windows\Fonts\yumin.ttf', r'C:\Windows\Fonts\msmincho.ttc', r'C:\Windows\Fonts\BIZ-UDMinchoM.ttc', r'C:\Windows\Fonts\yumindb.ttf']
def candidates():
    cs = []
    for hi in list(range(0x81, 0xA0)) + list(range(0xE0, 0xEB)):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F: continue
            try: c = bytes([hi, lo]).decode('cp932')
            except: continue
            if c.isprintable() and c != '\u3000': cs.append(c)
    cs += [chr(c) for c in range(0x21, 0x7f)]
    cs += list('①②③④⑤⑥⑦⑧⑨⑩')
    return sorted(set(cs))
N = 26
def prep(a):
    """a: (26,26) float 잉크 -> 흐린 뒤 정규화 벡터"""
    im = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    v = np.asarray(im, np.float32).reshape(-1); v = v - v.mean()
    n = np.linalg.norm(v); return v / n if n else v
def render(c, fp, size):
    f = ImageFont.truetype(fp, size)
    im = Image.new('L', (N, N), 0); d = ImageDraw.Draw(im)
    l, t, r, b = d.textbbox((0, 0), c, font=f)
    # 글꼴 em 기준 위치(가운데 정렬, 기준선 고정) — 작은 가나 크기 정보 보존
    asc, desc = f.getmetrics()
    x = (N - (r - l)) / 2 - l if (r-l) > 0 else 0
    y = (N - size) / 2 - (asc - size) + 0 
    d.text((x, y - 1), c, fill=255, font=f)
    return np.asarray(im, np.float32) / 255
def bank(cands, shifts=((0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(2,0),(0,2),(-2,0),(0,-2))):
    vecs = []; labels = []
    for fp in FONTS:
        for size in (22, 20):
            for c in cands:
                a = render(c, fp, size)
                for dx, dy in shifts[:5]:
                    vecs.append(prep(np.roll(np.roll(a, dy, 0), dx, 1))); labels.append(c)
    return np.stack(vecs), labels
