"""오프닝 동영상(prologue.sfd) 일본어 내레이션 자막 → 한국어 (게임 내 도입부 번역 0:1290:root:0002 사용).

페이지 표(PAGES): 영상 프레임 구간 → 도입부 번역 페이지 번호 (영상 전용 문장 2개는 V1, V2).
자막 상자 안의 일본어(본문·후리가나·빨간 글자)를 지우고(inpaint) 한국어를 다시 그린다.
"""
import json, re, glob
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = str(ROOT / 'SeoulHangangB.ttf')
TOKEN = re.compile(r'(<[0-9A-F]{4}(?:,[0-9A-F]{4})*>)')

# (시작 프레임, 끝 프레임, 페이지)
PAGES = [(306,371,0),(390,457,1),(465,540,2),(576,634,3),(659,734,4),(901,975,5),(1002,1074,6),(1099,1171,7),
 (1192,1270,8),(1290,1365,9),(1470,1546,10),(1573,1646,11),(1670,1749,12),(1770,1843,13),(1861,1940,14),
 (1970,2042,15),(2108,2182,16),(2207,2291,17),(2315,2395,18),(2477,2555,19),(2556,2646,20),(2655,2734,21),
 (2820,2897,22),(2932,3009,23),(3044,3108,24),(3137,3220,25),(3265,3338,26),(3345,3421,27),(3455,3529,28),
 (3564,3635,29),(3672,3738,30),(3759,3835,31),(3872,3943,32),(3960,4025,33),(4033,4095,34),(4096,4195,35),
 (4196,4288,36),(4289,4352,37),(4353,4440,38),(4441,4540,39),(4541,4612,40),(4613,4700,41),(4701,4800,42),
 (4927,5001,43),(5037,5157,44),(5467,5543,45),(5552,5619,46),(5641,5713,47),(5722,5799,48),(5826,5907,49),
 (5925,6006,50),(6055,6129,51),(6148,6216,52),(6237,6306,53),(6338,6401,54),(6510,6581,55),(6804,6862,56),
 (6863,6941,57),(6968,7035,58),(7050,7112,59),(7133,7203,60),(7228,7305,61),(7461,7539,62),(7568,7637,63),
 (7662,7735,64),(7772,7838,65),(7877,7956,66),(8041,8116,67),(8137,8216,68),(8245,8313,69),(8322,8395,70),
 (8581,8672,71),(8689,8765,72),(8794,8865,73),(8890,8975,'V1'),(9002,9063,'V2')]
EXTRA = {'V1': '그리고 평화의 초석이 된<A001><B602,0001>용감하고 신령한 늑대<B301>를 —',
         'V2': '경애와 존숭의 마음을 담아<A001>이렇게 불렀단다'}
BOX = (66, 326, 580, 428)          # 자막 상자 안쪽(x0,y0,x1,y1)

def korean_pages():
    texts = {}
    for p in glob.glob(str(ROOT / 'translation/*_ko.json')):
        texts.update(json.load(open(p, encoding='utf-8')))
    t = texts['0:1290:root:0002']
    pages = [p for p in t.split('<A301>') if TOKEN.sub('', p).strip()]
    return pages

def page_lines(page):
    """[[(텍스트, 빨강여부), ...], ...] 줄 목록"""
    lines = []
    for raw in page.split('<A001>'):
        segs = []; red = False
        for span in TOKEN.split(raw):
            if not span: continue
            if TOKEN.fullmatch(span):
                if span.startswith('<B602'): red = True
                elif span.startswith('<B301'): red = False
                continue
            segs.append((span, red))
        if segs: lines.append(segs)
    return lines

_FONT = None
def render(img, lines, size=23, gap=31):
    global _FONT
    if _FONT is None: _FONT = ImageFont.truetype(FONT, size)
    f = _FONT
    x0, y0, x1, y1 = BOX
    cy = 377
    n = len(lines); top = cy - gap * (n - 1) / 2
    im = Image.fromarray(img); d = ImageDraw.Draw(im)
    for li, segs in enumerate(lines):
        w = sum(d.textlength(s, font=f) for s, _ in segs)
        x = (x0 + x1) / 2 - w / 2; y = top + li * gap
        for s, red in segs:
            col = (190, 25, 20) if red else (36, 30, 26)
            d.text((x, y), s, font=f, fill=col, anchor='lm')
            x += d.textlength(s, font=f)
    return np.asarray(im)

def erase(img):
    x0, y0, x1, y1 = BOX
    reg = img[y0:y1, x0:x1].copy()
    g = cv2.cvtColor(reg, cv2.COLOR_RGB2GRAY).astype(np.int16)
    bg = cv2.medianBlur(g.astype(np.uint8), 21).astype(np.int16)
    r, gg = reg[..., 0].astype(np.int16), reg[..., 1].astype(np.int16)
    mask = ((bg - g) > 38) | ((r - gg) > 45)
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=2)
    reg = cv2.inpaint(reg, mask, 4, cv2.INPAINT_TELEA)
    out = img.copy(); out[y0:y1, x0:x1] = reg
    return out

def frame_page():
    """프레임 번호 → 페이지(본문 줄 목록)"""
    pages = korean_pages(); m = {}
    prev_end = -1
    spans = []
    for a, b, p in PAGES:
        # 글자가 한두 개 찍히는 첫 프레임들은 검출에서 빠지므로 앞 페이지 끝 직후까지 앞당긴다(최대 40프레임)
        a2 = max(prev_end + 2, a - 40); spans.append((a2, b, p)); prev_end = b
    for a, b, p in spans:
        txt = EXTRA[p] if isinstance(p, str) else pages[p]
        L = page_lines(txt)
        for f in range(a, b + 2): m[f] = L
    return m

def apply(img, lines):
    return render(erase(img), lines)
