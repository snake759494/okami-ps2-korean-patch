"""오오카미 공통 컨테이너: u32 개수, u32 오프셋[개수], 4바이트 태그[개수], 16정렬."""
import struct
def is_pack(d):
    if len(d) < 8: return False
    c = struct.unpack_from('<I', d, 0)[0]
    if not 1 <= c <= 4096 or 4 + 8 * c > len(d): return False
    offs = struct.unpack_from('<%dI' % c, d, 4)
    if offs[0] != (4 + 8 * c + 15) // 16 * 16 and offs[0] < 4 + 8 * c: return False
    if offs[0] < 4 + 8*c or offs[0] > 4 + 8*c + 32: return False
    for a, b in zip(offs, offs[1:]):
        if b < a: return False
    if offs[-1] > len(d): return False
    return True
def parse(d):
    c = struct.unpack_from('<I', d, 0)[0]
    offs = list(struct.unpack_from('<%dI' % c, d, 4))
    tags = [d[4+4*c+4*i:8+4*c+4*i].rstrip(b'\0').decode('latin1') for i in range(c)]
    ends = offs[1:] + [len(d)]
    return [(tags[i], offs[i], ends[i]) for i in range(c)]
def build(items, tags, end_align=16):
    """items: bytes 리스트 (원본 정렬과 같게 16 정렬)."""
    c = len(items)
    h = 4 + 8 * c; h = (h + 15) // 16 * 16
    out = bytearray(h); struct.pack_into('<I', out, 0, c)
    for i, (b, t) in enumerate(zip(items, tags)):
        struct.pack_into('<I', out, 4 + 4*i, len(out))
        out[4+4*c+4*i:8+4*c+4*i] = t.encode('latin1').ljust(4, b'\0')
        out += b
        while len(out) % 16: out.append(0)
    return bytes(out)
def walk(d, path=''):
    """(path, tag, bytes) 재귀 순회."""
    if not is_pack(d): return
    for i, (t, a, b) in enumerate(parse(d)):
        sub = d[a:b]; p = '%s/%d.%s' % (path, i, t)
        yield p, t, sub
        yield from walk(sub, p)
