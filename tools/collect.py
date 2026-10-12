"""모든 메시지 블록(MSD+MSA+MST) 수집: work/blocks.pkl
항목: dict(file, path, msd, msa, mst, kind) — path 는 파일 안 컨테이너 경로(인덱스 목록)."""
import sys, os, pickle, hashlib
sys.path.insert(0, os.path.dirname(__file__))
import afs, pack
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
def find(d, path=()):
    if not pack.is_pack(d): return
    P = pack.parse(d); tags = [t for t, a, b in P]
    for i, (t, a, b) in enumerate(P):
        if t == 'MSD':
            def near(tag):
                c = [j for j, x in enumerate(tags) if x == tag]
                c.sort(key=lambda j: (j < i, abs(j - i)))
                return c[0] if c else None
            yield dict(path=path, i_msd=i, i_msa=near('MSA'), i_mst=near('MST'))
    for i, (t, a, b) in enumerate(P):
        yield from find(d[a:b], path + (i,))
def sub(d, path):
    for i in path:
        P = pack.parse(d); d = d[P[i][1]:P[i][2]]
    return d
def main():
    idx = afs.index(); out = []
    for n, (k, o, s) in sorted(idx.items()):
        if s > 30_000_000: continue
        d = afs.read(k, o, s)
        for b in find(d):
            c = sub(d, b['path']); P = pack.parse(c)
            g = lambda i: c[P[i][1]:P[i][2]] if i is not None else None
            b.update(file=n, msd=g(b['i_msd']), msa=g(b['i_msa']), mst=g(b['i_mst']))
            out.append(b)
    pickle.dump(out, open(os.path.join(ROOT, 'work', 'blocks.pkl'), 'wb'))
    print(len(out))
if __name__ == '__main__': main()
