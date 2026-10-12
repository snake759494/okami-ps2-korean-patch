"""오오카미 _DATA0/_DATA1.AFS 읽기 (ISO 안에서 직접)."""
import os, struct
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ISO = os.path.join(ROOT, 'Ookami (Japan).iso')
AFS_LBA = {0: 3224, 1: 1051901}
AFS_SIZE = {0: 2147690496, 1: 2104313856}

def toc(k, iso=ISO):
    with open(iso, 'rb') as f:
        base = AFS_LBA[k] * 2048
        f.seek(base); h = f.read(8); n = struct.unpack_from('<I', h, 4)[0]
        t = f.read(n * 8 + 8)
        ent = [struct.unpack_from('<II', t, i * 8) for i in range(n + 1)]
        no, ns = ent[n]
        f.seek(base + no); nt = f.read(ns)
    out = []
    for i in range(n):
        nm = nt[i*48:i*48+32].split(b'\0')[0].decode('latin1')
        out.append((nm, ent[i][0], ent[i][1]))
    return out, (no, ns), ent

def read(k, off, size, iso=ISO):
    with open(iso, 'rb') as f:
        f.seek(AFS_LBA[k] * 2048 + off); return f.read(size)

def index(iso=ISO):
    """이름 -> (afs, off, size)"""
    d = {}
    for k in (0, 1):
        for nm, o, s in toc(k, iso)[0]:
            d[nm] = (k, o, s)
    return d
