"""공통 글꼴 198~717번을 원본 검수 시트와 대조한 판독 기록."""
import json,pickle
from pathlib import Path
import font
ROOT=Path(__file__).resolve().parents[1]
lines={
198:'事上来度気前者間何描立言姿込今持心悪攻野回全満食公知様思光最自話落後敵情先戻開続世向',
240:'記下不当空待突外手入異袋',
252:'珠百再集唯我独尊数完成仮',
264:'現退治太陽器旅助々物格納',
276:'溜幸玉神通力強化出道中筆',
288:'確認路導多報録國地図紐解',
300:'在位置扇閉断咲花蓮蔦風幽',
312:'燃爆弓濡壁撃蘇凍輝女郎蜘',
324:'蛛答選坊丸疾飛梅竹介智狗',
336:'孝礼信悌男素体爺漁師父取',
348:'翁桃姫阿国大臣踊子供婆都',
360:'畑母行商人兵士虚無僧名舌',
372:'切小柄鬼斬斎夫仲居頭井戸',
384:'端見張番分温泉客親方憧松',
396:'流衛門具屋武亭真澄桜早蔵',
408:'舶侍宿将宝帝貴族隊三茶老',
420:'亀警備九十尾天邪望岬動好',
432:'笹部郷主面側近料理長味美',
444:'骨頂産墨破魔札飾除鈴復限',
456:'魚古銭黄金経津鏡獣沖辺八',
468:'咫足生返死尺瓊勾牟刈刀七',
480:'支草薙剣握叢雲妖怪牙焼根',
492:'参白菜餅米俵肉団御飯巻果',
504:'煮饅釜木遺跡変形里印籠打',
516:'槌砦龍管雷酒貝殻守紗灯肝',
528:'氷唇輪朱目黒角忠仁義1両',
540:'用ID05任意移身業絶景',
552:'絵伝説樹歯車北塩折之月民',
564:'閃弐二文明存極戦穴掘秘訣',
576:'炭竿雪宗箱香調合薬粉快鮪',
588:'紅奥書水迅餌付逃走画点紋',
600:'所霧隠豆刺招猫枕銘鋼捌石',
612:'簡火避砥禁磁壺谷皿炉銀懐',
624:'時計干丑漆彫熊摩尼欠片晶',
636:'鎮寅卯辰巳午未申酉戌亥琥',
648:'珀翡翠帰六五四本滝鯛縦縞',
660:'宮使伊勢海夜祠敷島殿畳闘',
672:'結評価総川村窟州平原家口',
684:'森場社船着曇淵狩高関難西',
696:'安京庶街館刻寺展鳴塔内扉',
708:'舟鐘乳洞室山麓②広岩',
}
assert len(lines[198])==42
assert all(len(v)==(10 if k==708 else 42 if k==198 else 12) for k,v in lines.items())
b=next(x for x in pickle.loads((ROOT/'work/all_blocks.pkl').read_bytes()) if x['file']=='core.bin')
a=font.msa_parse(b['msa']);pixels=font.decode(b['mst'])
dest=ROOT/'work/glyph_labels.json';labels=json.loads(dest.read_text(encoding='utf8'));edits=[]
for start,text in lines.items():
    for i,char in enumerate(text,start):
        j=i//2;x=j%(a['w']//26)*26;y=j//(a['w']//26)*26
        key=((pixels[y:y+26,x:x+26]>>(2*(1-(i&1))))&3).tobytes().hex()
        if labels.get(key)!=char:edits.append(dict(index=i,before=labels.get(key),after=char,key=key))
        labels[key]=char
dest.write_text(json.dumps(labels,ensure_ascii=False),encoding='utf8')
(ROOT/'work/core_kanji_corrections.json').write_text(json.dumps(dict(evidence='work/core_glyph_review/*.png',reviewed=520,changes=edits),ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([dict(index=e['index'],before=e['before'],after=e['after']) for e in edits],ensure_ascii=False,indent=2))
