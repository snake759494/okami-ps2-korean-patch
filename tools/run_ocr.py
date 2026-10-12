import sys, os, pickle, json, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import font, ocr
B = pickle.load(open('work/blocks.pkl', 'rb'))
uniq = {}; refs = []
for bi, b in enumerate(B):
    a = font.msa_parse(b['msa'])
    if a['n'] == 0: refs.append([]); continue
    G = font.glyphs(b['msa'], b['mst']); r = []
    for g in G:
        k = g.tobytes(); uniq.setdefault(k, g); r.append(k)
    refs.append(r)
keys = list(uniq); print('uniq glyphs', len(keys))
def ink(g): return np.where(g == 0, 0, np.where(g == 1, 1.0, np.where(g == 2, .7, .45)))
Q = []
SH = [(0,0),(1,0),(-1,0),(0,1),(0,-1),(2,0),(-2,0),(0,2),(0,-2),(1,1),(-1,-1),(1,-1),(-1,1)]
for k in keys:
    a = ink(uniq[k]); Q.append([ocr.prep(np.roll(np.roll(a, dy, 0), dx, 1)) for dx, dy in SH])
Q = np.array(Q, np.float32)  # (n, S, 676)
cands = ocr.candidates(); print('cands', len(cands))
M = []; L = []
for fp in ocr.FONTS[:3]:
    for c in cands:
        M.append(ocr.prep(ocr.render(c, fp, 22))); L.append(c)
M = np.array(M, np.float32).T
best = np.full(len(keys), -9.0, np.float32); arg = np.zeros(len(keys), np.int64); top = []
S = Q.reshape(-1, Q.shape[2]) @ M  # (n*S, m)
S = S.reshape(len(keys), len(SH), -1).max(1)
res = {}
for i, k in enumerate(keys):
    o = np.argsort(-S[i])
    seen = []; 
    for j in o:
        if L[j] not in [x[0] for x in seen]: seen.append((L[j], float(S[i, j])))
        if len(seen) >= 4: break
    res[k.hex()] = seen
json.dump(dict(res=res, refs=[[k.hex() for k in r] for r in refs]), open('work/ocr.json', 'w'), ensure_ascii=False)
