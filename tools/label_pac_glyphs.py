"""새 고정 레코드에서 찾은 69개 원본 글리프를 눈으로 판독한 결과."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'work/unidentified_glyphs.json'
keys=list(json.loads(source.read_text(encoding='utf8')))
if not keys:
    keys=json.loads((ROOT/'work/pac_glyph_review.json').read_text(encoding='utf8'))['keys']
characters='遑罵罠煽錫杖侮蔑拍跨喝磊悼狗塚柔蓑鰭含雇靡喪飄痺鮫恰沿隆冑膚掠煩献善稀慕欺鷹蛮翳睦叡猪農囚釈研譚婀酬潤烙費軌摯魑魍魎但弊呱∞滓曾訶穹殆俯弧'
assert len(keys)==len(characters)==69
dest=ROOT/'work/glyph_labels.json';labels=json.loads(dest.read_text(encoding='utf8'))
for key,char in zip(keys,characters):
    assert key not in labels or labels[key]==char
    labels[key]=char
dest.write_text(json.dumps(labels,ensure_ascii=False),encoding='utf8')
(ROOT/'work/pac_glyph_review.json').write_text(json.dumps(dict(count=69,characters=list(characters),keys=keys,evidence='new_pac_glyphs.png and new_pac_glyphs_detail.png; original pixel inspection',reviewer='assistant'),ensure_ascii=False,indent=2),encoding='utf8')
