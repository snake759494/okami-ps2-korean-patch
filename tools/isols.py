"""ISO9660 디렉터리 전체 목록 (lba, size, path)."""
import sys, struct
ISO = sys.argv[1]
f = open(ISO, 'rb')
def sec(l, n=1):
    f.seek(l*2048); return f.read(2048*n)
pvd = sec(16)
root = pvd[156:156+34]
def walk(lba, size, path):
    d = sec(lba, (size+2047)//2048); i = 0
    while i < len(d):
        L = d[i]
        if L == 0: i = (i//2048+1)*2048; continue
        r = d[i:i+L]; el, sz = struct.unpack_from('<I', r, 2)[0], struct.unpack_from('<I', r, 10)[0]
        fl = r[25]; nl = r[32]; nm = r[33:33+nl]
        if nm not in (b'\0', b'\1'):
            n = nm.decode('latin1')
            if fl & 2: walk(el, sz, path + n + '/')
            else: print(el, sz, path + n)
        i += L
walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '/')
