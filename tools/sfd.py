"""Sofdec SFD(MPEG-1 시스템 스트림, 영상 MPEG-2 ES E0, 음성 ADX C0) 분석·영상 교체."""
import struct

def packets(d):
    """[(kind, off, sid, hdr_end, end)]  kind: pack/pes/end. PES 헤더(MPEG-1) 끝 위치 포함."""
    out = []; i = 0; n = len(d)
    while i + 4 <= n:
        j = d.find(b'\0\0\1', i)
        if j < 0: break
        sid = d[j + 3]
        if sid == 0xBA:
            L = 12 if (d[j + 4] >> 4) == 2 else 14 + (d[j + 13] & 7)
            out.append(('pack', j, sid, j + L, j + L)); i = j + L
        elif sid == 0xB9:
            out.append(('end', j, sid, j + 4, j + 4)); i = j + 4
        elif sid >= 0xBB:
            ln = int.from_bytes(d[j + 4:j + 6], 'big'); end = j + 6 + ln
            h = j + 6
            if sid not in (0xBB, 0xBE, 0xBF):
                while d[h] == 0xFF: h += 1
                if d[h] >> 6 == 1: h += 2
                f = d[h] >> 4
                h += 5 if f == 2 else 10 if f == 3 else 1
            out.append(('pes', j, sid, h, end)); i = end
        else:
            i = j + 3
    return out

def video_es(d, P=None):
    P = P or packets(d)
    return b''.join(d[h:e] for k, o, s, h, e in P if k == 'pes' and s == 0xE0)

def pictures(es):
    """디코드 순서 그림: [off, type(1=I,2=P,3=B), display_index]; GOP 시작 오프셋 목록."""
    pics = []; gops = []; base = 0; cnt = 0
    i = es.find(b'\0\0\1')
    while 0 <= i and i + 6 <= len(es):
        c = es[i + 3]
        if c == 0xB8:
            base += cnt; cnt = 0; gops.append(i)
        elif c == 0x00:
            tr = (es[i + 4] << 2) | (es[i + 5] >> 6); pt = (es[i + 5] >> 3) & 7
            pics.append([i, pt, base + tr]); cnt += 1
        i = es.find(b'\0\0\1', i + 3)
    return pics, gops
