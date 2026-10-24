"""UI 텍스처의 일본어 라벨을 한글로 교체. 원본 글자가 있던 상자(대략) 안의 잉크를 지우고
같은 색으로 서울한강체 B 를 상자에 맞춰(필요하면 가로 압축) 그린다. 크기·팔레트 불변."""
import json, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import tex
ROOT = Path(__file__).resolve().parents[1]
FONT = str(ROOT / 'SeoulHangangB.ttf')

def render(text, w, h, align='c'):
    """w×h 안에 맞춘 커버리지(0..1)."""
    size = max(6, int(h * 0.92))
    while True:
        f = ImageFont.truetype(FONT, size)
        im = Image.new('L', (w * 4, h * 2)); d = ImageDraw.Draw(im)
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        if b - t <= h or size <= 6: break
        size -= 1
    im = Image.new('L', (r - l + 2, b - t + 2)); d = ImageDraw.Draw(im)
    d.text((1 - l, 1 - t), text, font=f, fill=255)
    tw = min(w, im.width)
    if im.width > w: im = im.resize((w, im.height), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255
    out = np.zeros((h, w), np.float32)
    oy = (h - a.shape[0]) // 2; ox = (w - a.shape[1]) // 2 if align == 'c' else (w - a.shape[1] if align == 'r' else 0)
    out[max(0, oy):max(0, oy) + min(h, a.shape[0]), max(0, ox):max(0, ox) + min(w, a.shape[1])] = a[:min(h, a.shape[0]), :min(w, a.shape[1])]
    return out

def apply(raw, labels):
    """label: [x0,y0,x1,y1,text, opts]
    opts.fg=[r,g,b]  : 이 색에 가까운 픽셀만 글자로 보고(색 배경 위 글자) 지운 자리는 주변 배경색으로 메움
    opts.ol=[r,g,b]  : 외곽선 색(원본 외곽선도 함께 지우고 새 글자에 1px 외곽선)
    opts.full=true   : 원본 잉크 상자 대신 지정 상자 전체에 맞춤"""
    t = tex.load(raw); pal = t['pal']; idx = t['idx']
    alpha = pal[:, 3]; clear = int(np.argmin(alpha))
    for lab in labels:
        x0, y0, x1, y1, text = lab[:5]; o = lab[5] if len(lab) > 5 else {}
        if o.get('erase_all'):
            # 원본 잉크 색을 기억한 뒤 전체를 지우고, 필요하면 사각 테두리를 그린다
            ink0 = alpha[idx] > 8
            vals, cnt = np.unique(idx[ink0], return_counts=True)
            keep = int(vals[cnt.argmax()]) if len(vals) else tex.nearest(pal, (255, 255, 255, 128))
            idx[:] = clear
            th = o.get('frame', 0)
            if th:
                idx[y0:y0 + th, x0:x1] = keep; idx[y1 - th:y1, x0:x1] = keep
                idx[y0:y1, x0:x0 + th] = keep; idx[y0:y1, x1 - th:x1] = keep
            continue
        reg = idx[y0:y1, x0:x1]
        if 'fg' in o:
            rgb = pal[reg][..., :3]
            def near(c, th=80): return (np.abs(rgb - np.asarray(c)).sum(-1) < th) & (alpha[reg] > 8)
            ink = near(o['fg'])
            if 'ol' in o: ink |= near(o['ol'], 60)
            nonink = reg[~ink & (alpha[reg] > 8)] if (~ink & (alpha[reg] > 8)).any() else reg[~ink]
            v, c = np.unique(nonink, return_counts=True); fill = int(v[c.argmax()]) if len(v) else clear
            # 가장자리 잔상: 글자 주변(o.grow 픽셀)에서 배경색과 거리가 먼 픽셀까지 함께 지움
            frgb = pal[fill][:3]; far = np.abs(rgb - frgb).sum(-1) > o.get('bgtol', 60)
            g = ink.copy()
            for _ in range(o.get('grow', 2)):
                g2 = g.copy()
                for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)): g2 |= np.roll(np.roll(g, dy, 0), dx, 1)
                g = g2
            ink = ink | (g & far)
            col = np.array(list(o['fg']) + [int(alpha.max())])
        else:
            ink = alpha[reg] > 8
            if 'ol' in o:
                pass
            if ink.any():
                vals, cnt = np.unique(reg[ink], return_counts=True); col = pal[vals[cnt.argmax()]].copy()
            else: col = np.array([255, 255, 255, 128])
            if 'color' in o: col = np.array(list(o['color']) + [int(alpha.max())])
            fill = clear
        if ink.any() and not o.get('full'):
            ys, xs = np.nonzero(ink); bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        else: bx0, by0, bx1, by1 = 0, 0, x1 - x0, y1 - y0
        reg[ink] = fill
        pad = 1 if 'ol' in o else 0
        cov = render(text, int(bx1 - bx0) - 2 * pad, int(by1 - by0) - 2 * pad, o.get('align', 'c'))
        if pad: cov = np.pad(cov, pad)
        sub = reg[by0:by1, bx0:bx1]
        if 'ol' in o:
            m = cov > 0.3; d = m.copy()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1): d |= np.roll(np.roll(m, dy, 0), dx, 1)
            oc = tex.nearest(pal, list(o['ol']) + [int(alpha.max())])
            sub[d & ~m] = oc
        for yy in range(cov.shape[0]):
            for xx in range(cov.shape[1]):
                c = cov[yy, xx]
                if c < 0.12: continue
                if 'fg' in o and c < 0.5: continue
                sub[yy, xx] = tex.nearest(pal, (col[0], col[1], col[2], col[3] * min(1.0, c * 1.15)))
    t['idx'] = idx
    return tex.save(raw, t)

if __name__ == '__main__':
    pass

def apply_board(raw, boxes, font_px=19):
    """설명판(두루마리 상자)용: 상자 안을 상자 배경색으로 칠하고 여러 줄 글자를 다시 쓴다.
    boxes: [[x0,y0,x1,y1,[줄,...]], ...]  줄 안의 [ ... ] 은 빨간 글자."""
    import re as _re
    t = tex.load(raw); pal = t['pal']; idx = t['idx']
    black = tex.nearest(pal, (20, 20, 20, 128)); red = tex.nearest(pal, (200, 20, 20, 128))
    for x0, y0, x1, y1, lines in boxes:
        reg = idx[y0:y1, x0:x1]
        lum = pal[reg][..., :3].sum(-1)
        bgv, cnt = np.unique(reg[lum > 450], return_counts=True)
        bg = int(bgv[cnt.argmax()])
        reg[:] = bg
        W, H = x1 - x0, y1 - y0; n = len(lines)
        size = font_px
        while True:
            f = ImageFont.truetype(FONT, size)
            widths = [ImageDraw.Draw(Image.new('L', (1, 1))).textlength(_re.sub(r'[\[\]]', '', l), font=f) for l in lines]
            if (max(widths) <= W - 8 and size * 1.25 * n <= H) or size <= 10: break
            size -= 1
        lh = H / n
        for li, line in enumerate(lines):
            y = int(li * lh + (lh - size) / 2) - 1
            x = 6.0
            for part in _re.split(r'(\[[^\]]*\])', line):
                if not part: continue
                col = red if part.startswith('[') else black
                txt = part.strip('[]')
                im = Image.new('L', (W, H)); d = ImageDraw.Draw(im)
                d.text((x, y), txt, font=f, fill=255)
                a = np.asarray(im)
                reg[a >= 110] = col
                x += d.textlength(txt, font=f)
    t['idx'] = idx
    return tex.save(raw, t)
