"""TBL 안에 숨어 있어 기존 추출에서 빠진 메시지 블록(MSD+MSA+MST PAC) 추출.
결과: work/missed_blocks.pkl (블록), translation/missed_source.json (원문 행)
행 id = 'M:<archive>:<index>:<PAC오프셋16진>:<메시지번호>'"""
import json, pickle, re, struct
from pathlib import Path
import afs, pack, msd, font
ROOT = Path(__file__).resolve().parents[1]

def scan():
    B = pickle.loads((ROOT / 'work/all_blocks.pkl').read_bytes())
    known = set(b['msd'] for b in B if b['msd'])
    out = []
    for k in (0, 1):
        for i, (n, o, s) in enumerate(afs.toc(k)[0]):
            if s > 40_000_000: continue
            d = afs.read(k, o, s)
            for mt in re.finditer(rb'MSD\x00MSA\x00MST\x00|MSD\x00MST\x00MSA\x00', d):
                h = mt.start() - 16
                if h < 0 or struct.unpack_from('<I', d, h)[0] != 3: continue
                end_guess = None
                P = pack.parse(d[h:h + 0x10000000]) if pack.is_pack(d[h:]) else None
                if not P: continue
                tags = [t for t, a, b in P]
                offs = [a for t, a, b in P]
                # PAC 끝: 마지막 항목 끝 = MST 의 TIM 전체 크기로 계산
                parts = {}
                for j, t in enumerate(tags):
                    a = h + offs[j]
                    b = h + offs[j + 1] if j + 1 < 3 else None
                    parts[t] = (a, b)
                ma, _ = parts['MST'] if tags[-1] == 'MST' else parts[tags[-1]]
                last = tags[-1]
                la = parts[last][0]
                if last == 'MST':
                    tot = struct.unpack_from('<I', d, la + 16)[0]; lb = la + 16 + tot
                    # CLUT 뒤 후행 데이터(팔레트 블록)는 다음 16정렬까지
                    hd = font.tim_hdr(d[la:la + 64]); lb = la + hd['img'] + hd['imsz'] + 640
                else:
                    lb = la + 8 + 4 * struct.unpack_from('<H', d, la)[0]
                parts[last] = (la, lb)
                pe = (lb + 15) // 16 * 16
                msdb = d[parts['MSD'][0]:parts['MSD'][1]]
                if msdb in known: continue
                out.append(dict(archive=k, index=i, file=n, pac_off=h, pac_end=pe, tags=tags,
                                msd=msdb, msa=d[parts['MSA'][0]:parts['MSA'][1]], mst=d[parts['MST'][0]:parts['MST'][1]]))
    return out

def main():
    blocks = scan()
    labels = json.loads((ROOT / 'work/glyph_labels.json').read_text(encoding='utf-8'))
    B = pickle.loads((ROOT / 'work/all_blocks.pkl').read_bytes())
    core = next(b for b in B if b['file'] == 'core.bin')
    cg = font.glyphs(core['msa'], core['mst'])
    rows = []; unknown = 0
    for b in blocks:
        lg = font.glyphs(b['msa'], b['mst']) if len(b['mst']) > 64 and font.msa_parse(b['msa'])['n'] else []
        def ch(v):
            nonlocal unknown
            g = cg[v ^ 1] if v >> 12 == 0 and (v ^ 1) < len(cg) else (lg[(v & 4095) ^ 1] if ((v & 4095) ^ 1) < len(lg) else None)
            if g is None: unknown += 1; return '〓'
            c = labels.get(g.tobytes().hex())
            if c is None: unknown += 1; return '〓'
            return c
        for mi, item in enumerate(msd.parse(b['msd'])):
            if item is None: continue
            words = item[0]; s = ''; i = 0
            while i < len(words):
                v = words[i]
                if v >= 0x8000:
                    n = v & 255; s += '<' + ','.join('%04X' % x for x in words[i:i + n]) + '>'; i += n; continue
                s += ch(v); i += 1
            rows.append(dict(id='M:%d:%04d:%x:%04d' % (b['archive'], b['index'], b['pac_off'], mi),
                             file=b['file'], source=s))
    pickle.dump(blocks, open(ROOT / 'work/missed_blocks.pkl', 'wb'))
    (ROOT / 'translation/missed_source.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print('블록', len(blocks), '메시지', len(rows), '미식별 글리프', unknown)

if __name__ == '__main__': main()
