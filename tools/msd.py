"""MSD 메시지 블록: u16 n, u16 미상, (u32 본문오프셋, u32 루비오프셋)[n], u16 문자열(0x8001 끝)."""
import struct
END = 0x8001
def parse(m):
    n = struct.unpack_from("<H", m, 0)[0]
    out = []
    for i in range(n):
        a, r = struct.unpack_from('<II', m, 4 + 8 * i)
        if a == 0:
            out.append(None); continue
        s = []; p = a
        while True:
            v = struct.unpack_from('<H', m, p)[0]; p += 2; s.append(v)
            if v == END: break
        ruby = None
        if r:
            ruby = []; p = r
            while True:
                v = struct.unpack_from('<H', m, p)[0]
                if v == 0xffff: break
                nb, nk = struct.unpack_from('<HH', m, p + 2)
                ruby.append((v, nb, list(struct.unpack_from('<%dH' % nk, m, p + 6)))); p += 6 + 2 * nk
        out.append((s, ruby))
    return out
