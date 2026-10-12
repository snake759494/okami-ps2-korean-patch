# 재빌드

번역 대본과 일본어 원문은 저장소에 포함하지 않으므로, 이 문서는 도구 구성과 순서를 설명합니다.

## 준비

- Python 3.11 이상, `numpy`, `Pillow`, `fontTools`, `zstandard`(검증용)
- 원본 `Ookami (Japan).iso` (README 의 해시와 일치)
- 서울한강체 B `SeoulHangangB.ttf` (서울특별시 배포본)

## 순서

```powershell
python -X utf8 tools/extract_all_text.py      # 메시지 블록 추출 → work/all_blocks.pkl, translation/all_source_draft.json
python -X utf8 tools/extract_missed.py        # TBL 안 누락 블록 추출 → work/missed_blocks.pkl, translation/missed_source.json
python -X utf8 tools/validate_translation.py  # 번역 파일(translation/*_ko.json) 제어 토큰 검사
python -X utf8 tools/build_preview_iso.py     # 글꼴·메시지·텍스처 빌드 + ISO 재구성 → Ookami (Japan) (Korean).iso
```

번역 파일 형식: `{"메시지 id": "번역문(원문과 같은 <XXXX,...> 제어 토큰)"}`. 누락 블록 번역은 `translation/*.mko.json`.
글자 그림 사양은 `translation/ui_labels.json` (`[x0, y0, x1, y1, 텍스트, 옵션]`).

## 주요 도구

| 파일 | 역할 |
| --- | --- |
| `afs.py`, `pack.py`, `fst.py`, `fixed_records.py` | AFS·컨테이너·FST·고정 레코드 |
| `msd.py`, `font.py`, `gsmem.py`, `tim2.py`, `tex.py` | 메시지·글꼴·텍스처 형식 |
| `build_resources.py`, `build_preview_iso.py`, `build_iso.py` | 글꼴·메시지 컴파일, AFS/ISO 재구성 |
| `wrap.py`, `linewidth.py` | 줄 폭 계산·자동 줄바꿈 |
| `relabel.py` | 글자 그림 교체 |
| `extract_*.py`, `ocr.py`, `run_ocr.py`, `kjsheet.py` | 원문 추출·글리프 판독 보조 |
| `emu.py` | 검증용 PCSX2(별도 사본) 조작 |
