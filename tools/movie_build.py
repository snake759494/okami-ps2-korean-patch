"""prologue.sfd 한국어 자막판 생성 → work/prologue_ko.sfd (원본과 같은 크기).

방법: 자막이 나오는 GOP 구간만 자막을 합성해 MPEG-2 로 다시 인코딩(닫힌 GOP 15장, B 없음: 디코드 순서=표시 순서라 앞뒤 원본의 PTS/DTS 시간축과 그대로 이어짐)하고,
원래 구간 바이트 수 안에 넣은 뒤 남는 자리는 0 으로 채운다(시작 코드 앞 0 채움은 규격상 허용).
원본은 시퀀스 헤더가 맨 앞에 하나뿐이고 별도 인트라 행렬을 쓰므로, 구간 앞에는 기본 행렬 헤더를,
구간 뒤 원본 GOP 앞에는 원본 헤더를 다시 넣는다. 음성·팩·패킷 위치는 바이트 그대로 두고,
바뀐 구간의 영상 패킷만 PTS/DTS 를 새 그림 위치에 맞게 다시 쓴다."""
import sys, os, bisect
from fractions import Fraction
from pathlib import Path
import numpy as np, av
import sfd, afs, movie_sub as MS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/prologue_ko.sfd'
IDX = (1, 1276)
PTS_A, PTS_B, DTS_B = 3003.0026, 86.6, 80.6

def wts(prefix, t):
    return bytes([(prefix << 4) | (((t >> 30) & 7) << 1) | 1, (t >> 22) & 255, (((t >> 15) & 127) << 1) | 1,
                  (t >> 7) & 255, ((t & 127) << 1) | 1])

ZZ = [0,1,8,16,9,2,3,10,17,24,32,25,18,11,4,5,12,19,26,33,40,48,41,34,27,20,13,6,7,14,21,28,
      35,42,49,56,57,50,43,36,29,22,15,23,30,37,44,51,58,59,52,45,38,31,39,46,53,60,61,54,47,55,62,63]

def matrices(hdr):
    """원본 시퀀스 헤더의 (intra, non-intra) 행렬 → 래스터 순서"""
    bits = ''.join(f'{x:08b}' for x in hdr[4:])
    def rd(p): return [int(bits[p + 8 * i:p + 8 + 8 * i], 2) for i in range(64)]
    def rast(z):
        r = [0] * 64
        for k, v in enumerate(z): r[ZZ[k]] = v
        return r
    p = 62; intra = inter = None
    if bits[p] == '1': intra = rast(rd(p + 1)); p += 513
    else: p += 1
    if bits[p] == '1': inter = rast(rd(p + 1))
    return intra, inter

MATS = None
def encode(frames, bitrate):
    """원본과 같은 양자화 행렬로 인코딩(ffmpeg) → 원본 시퀀스 헤더를 그대로 쓸 수 있다"""
    import subprocess, imageio_ffmpeg
    intra, inter = MATS
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', '640x448', '-r', '30000/1001', '-i', '-', '-c:v', 'mpeg2video', '-g', '15', '-bf', '0',
           '-flags', '+cgop', '-sc_threshold', '1000000000', '-b:v', str(int(bitrate)),
           '-maxrate', str(int(bitrate * 1.4)), '-bufsize', '1835008', '-pix_fmt', 'yuv420p']
    if intra: cmd += ['-intra_matrix', ','.join(map(str, intra))]
    if inter: cmd += ['-inter_matrix', ','.join(map(str, inter))]
    cmd += ['-f', 'mpeg2video', '-']
    r = subprocess.run(cmd, input=b''.join(np.ascontiguousarray(f).tobytes() for f in frames), capture_output=True)
    assert r.returncode == 0, r.stderr.decode(errors='replace')
    return r.stdout.replace(bytes([0,0,1,0xb7]), b'')

def fix_headers(es, run_hdr):
    """인코더의 시퀀스 헤더(+확장) 묶음을 run_hdr 로 바꾼다 (GOP 시작 코드 앞까지)."""
    out = bytearray(); i = 0
    while True:
        j = es.find(b'\0\0\1\xb3', i)
        if j < 0: out += es[i:]; break
        k = es.find(b'\0\0\1\xb8', j)
        out += es[i:j] + run_hdr; i = k
    return bytes(out)

def main():
    toc = afs.toc(IDX[0])[0]; _, o, s = toc[IDX[1]]
    d = afs.read(IDX[0], o, s)
    P = sfd.packets(d); es = sfd.video_es(d, P); pics, gops = sfd.pictures(es)
    first_gop = es.find(b'\0\0\1\xb8')
    orig_hdr = es[:first_gop]                      # 시퀀스 헤더(행렬 포함)+확장
    ext = orig_hdr[orig_hdr.find(b'\0\0\1\xb5'):]
    global MATS
    MATS = matrices(orig_hdr)
    run_hdr = b''   # 행렬이 같으므로 중간 시퀀스 헤더 없음
    gstart = gops + [len(es)]
    gop_of_dec = [bisect.bisect_right(gops, p[0]) - 1 for p in pics]
    disp2gop = {p[2]: gop_of_dec[i] for i, p in enumerate(pics)}
    fp = MS.frame_page()
    need = set()
    for f in fp:
        for g in range(f - 2, f + 18):
            if g in disp2gop: need.add(disp2gop[g])
    need = sorted(need); runs = []
    for g in need:
        if runs and runs[-1][1] == g: runs[-1][1] = g + 1
        else: runs.append([g, g + 1])
    info = []
    for ga, gb in runs:
        ds = sorted(p[2] for i, p in enumerate(pics) if ga <= gop_of_dec[i] < gb)
        assert ds == list(range(ds[0], ds[-1] + 1)), ('표시 순서 불연속', ga, gb)
        s0 = first_gop if ga == 0 else gstart[ga]; s1 = gstart[gb]
        tail = b''
        gl = [gstart[g + 1] - (first_gop if g == 0 else gstart[g]) for g in range(ga, gb)]
        gn = [sum(1 for i in range(len(pics)) if gop_of_dec[i] == g) for g in range(ga, gb)]
        info.append(dict(gl=gl, gn=gn, ga=ga, gb=gb, d0=ds[0], d1=ds[-1], s0=s0, s1=s1, budget=s1 - s0 - len(tail), tail=tail))
    print('구간', len(info), '프레임', sum(x['d1'] - x['d0'] + 1 for x in info), flush=True)
    # 디코드하며 구간별 인코딩
    c = av.open(av.open.__module__ and str(ROOT / 'work/_prologue_src.sfd')) if False else None
    tmp = ROOT / 'work/_prologue_src.sfd'; tmp.write_bytes(d)
    c = av.open(str(tmp)); ri = 0; buf = []; new_runs = []
    for fi, f in enumerate(c.decode(video=0)):
        if ri >= len(info): break
        r = info[ri]
        if fi < r['d0']: continue
        img = f.to_ndarray(format='rgb24')
        if fi in fp: img = MS.apply(img, fp[fi])
        buf.append(img)
        if fi == r['d1']:
            assert all(n == 15 for n in r['gn'][:-1]) and len(buf) == sum(r['gn']), ('GOP 15장 아님', r['ga'], r['gn'])
            br = min(r['gl']) * 8 / (15 / (30000 / 1001)) * 0.85
            for _ in range(12):
                enc = b''.join(fix_headers(encode(buf[k:k + 450], br), run_hdr) for k in range(0, len(buf), 450))
                np_, ng_ = sfd.pictures(enc)
                assert len(np_) == len(buf) and len(ng_) == len(r['gn']), ('그림/GOP 수 불일치', len(np_), len(ng_))
                gsz = [(ng_[k + 1] if k + 1 < len(ng_) else len(enc)) - ng_[k] for k in range(len(ng_))]
                worst = max(a / b for a, b in zip(gsz, r['gl']))
                if worst <= 1: break
                br *= 0.95 / worst
            assert worst <= 1, ('GOP 용량 초과', r['ga'], worst)
            # GOP 마다 원본 GOP 길이에 맞춰 배치, 그림 사이에 0 을 고르게 넣어 원본과 비슷한 속도로 도착하게 한다
            out = bytearray()
            for k in range(len(ng_)):
                g0 = ng_[k]; g1 = ng_[k + 1] if k + 1 < len(ng_) else len(enc)
                ps = [p[0] for p in np_ if g0 <= p[0] < g1]
                cuts = [g0] + ps[1:] + [g1]          # GOP 헤더+첫 그림, 이후 그림별
                L = r['gl'][k]; base = len(out); n = len(cuts) - 1
                for j in range(n):
                    rest = cuts[-1] - cuts[j]                 # 남은 그림 바이트 수
                    tgt = min(base + (L * j) // n, base + L - rest)
                    if len(out) < tgt: out += bytes(tgt - len(out))
                    out += enc[cuts[j]:cuts[j + 1]]
                assert len(out) <= base + L
                out += bytes(base + L - len(out))
            enc = bytes(out); assert len(enc) == r['budget'], (len(enc), r['budget'])
            new_runs.append(enc); print('run', ri, r['ga'], r['gb'], len(buf), 'worst %.2f' % worst, flush=True)
            buf = []; ri += 1
    c.close(); tmp.unlink()
    assert len(new_runs) == len(info)
    # 새 ES
    parts = []; pos = 0
    for r, enc in zip(info, new_runs):
        parts.append(es[pos:r['s0']])
        parts.append(enc + bytes(r['budget'] - len(enc)) + r['tail'])
        pos = r['s1']
    parts.append(es[pos:]); nes = b''.join(parts)
    assert len(nes) == len(es)
    npics, _ = sfd.pictures(nes)
    assert len(npics) == len(pics), (len(npics), len(pics))
    nstarts = [p[0] for p in npics]
    changed = [(r['s0'], r['s1']) for r in info]
    out = bytearray(d); epos = 0; nts = 0
    for k, off, sid, h, e in P:
        if k != 'pes' or sid != 0xE0: continue
        L = e - h; out[h:e] = nes[epos:epos + L]
        if any(a < epos + L and epos < b for a, b in changed):
            hs = off + 6; H = h - hs
            x = hs
            while out[x] == 0xFF: x += 1
            std = bytes(out[x:x + 2]) if out[x] >> 6 == 1 else b''
            f = out[x + len(std)] >> 4
            if f in (2, 3):
                q = bisect.bisect_left(nstarts, epos)
                if q < len(nstarts) and nstarts[q] < epos + L:
                    pts = int(round(PTS_A * npics[q][2] + PTS_B))
                    ts = wts(2, pts) if f == 2 else wts(3, pts) + wts(1, int(round(PTS_A * q + DTS_B)))
                else:
                    ts = b'\x0f'
                newh = b'\xff' * (H - len(std) - len(ts)) + std + ts
                assert len(newh) == H and H - len(std) - len(ts) <= 16
                out[hs:h] = newh; nts += 1
        epos += L
    assert epos == len(nes) and len(out) == len(d)
    OUT.write_bytes(bytes(out))
    print('완료', OUT, len(out), '헤더 재작성', nts)

if __name__ == '__main__':
    main()
