# 법안톡 60초 법안 쇼츠 템플릿

승인된 첫 쇼츠(`../shorts/건보특사경법_쇼츠.mp4`, 건보공단 특사경법)의 디자인을 그대로 두고,
**문구만 JSON으로 바꿔 끼우면** 다른 법안 쇼츠가 나오도록 만든 템플릿입니다.
JSON은 사람이 직접 써도 되고, `prompt.md`로 LLM에게 만들게 해도 됩니다.

- 1080×1920 세로, 30fps, 장면 6개(약 44초) — 찬반 자료가 없으면 4개(약 28초)
- 어두운 배경 · 파랑 강조 · 현재 단계 주황 · Noto Sans CJK KR (원본과 픽셀 단위로 동일하게 렌더됨을 확인)

## 폴더 구조

```
shorts-template/
├── render.py                 # 렌더러: JSON → 미리보기 PNG 또는 최종 mp4
├── schema.json               # JSON 스키마 (필드 정의)
├── prompt.md                 # LLM용 시스템/사용자 프롬프트 + 글자 수 한도 + 예시
├── data/
│   ├── gb-tsg.json                     # 원본 쇼츠(건보 특사경법)를 그대로 재현하는 데이터
│   ├── elder-care-housing.sources.md   # 두 번째 법안의 [자료] (기사 URL 포함)
│   └── elder-care-housing.json         # prompt.md를 적용해 만든 데이터
├── tests/minimal.json        # 필수 필드만 채운 검증용 데이터(찬반·다음 단계 없음, 가상의 예시)
├── outputs/                  # 최종 mp4 (elder-care-housing_쇼츠.mp4만 커밋)
└── build/                    # 임시 파일(장면 mp4, 미리보기) — git 제외
```

## 장면 구성

| # | 장면 | 길이 | 쓰는 필드 |
|---|---|---|---|
| 1 | 후킹 | 4.6초 | `category`, `hook.title_lines`, `hook.bill_name`(+기준일 자동), `hook.status`(+"현재:" 자동) |
| 2 | 무슨 법안이야? | 7.2초 | `what.summary_lines`, `what.cards` (비면 `bill_meta`의 발의자·발의일·소관위로 카드 대체) |
| 3 | 찬성 | 8.0초 | `pro.who`, `pro.quote_lines`, `pro.cards`(label/value/note), `pro.note` |
| 4 | 반대 | 7.6초 | `con.who`, `con.quote_lines`, `con.cards`(title/lines), `con.note` |
| 5 | 지금 어디까지 왔나? | 10.0초 | `status.stage`(0~5), `status.chip`, `status.details`, (`status.labels`) |
| 6 | 다음은? + 알림 버튼 | 6.4초 | `next.lines`, `next.note`, `next.cta_note`, `sources`(매체명·기간 자동) |

- 찬성·반대는 **둘 다 있거나 둘 다 없어야** 합니다. 둘 다 없으면 3·4번 장면을 건너뛰고 상단 진행 바도 4칸이 됩니다.
- `next.lines`가 비면 "국회 단계가 바뀔 때마다 바로 알려드려요" 기본 문구와 알림 버튼을 보여 줍니다.
- 후킹 제목이 4줄보다 짧으면 법안명·상태 칩이 위로 올라와 빈 공간을 줄입니다.
- `**강조**` 표기는 `hook.title_lines`(파랑), `what.summary_lines`·`next.lines`(주황)에서만 색이 바뀝니다.
- 진행 단계: 0 발의 · 1 소관위 회부 · 2 소관위 심사 · 3 법사위 체계·자구 · 4 본회의 · 5 정부 이송·공포.
  소관위가 법사위인 법안은 `status.labels`로 단계 이름을 바꿉니다(`data/gb-tsg.json`, `prompt.md` 3절 참고).

## JSON 만들기 (prompt.md 사용)

1. 법안 관련 기사·의안정보시스템 내용을 모아 `data/<id>.sources.md`로 정리합니다(매체·제목·URL·날짜 + 핵심 사실, 발언 주체).
2. `prompt.md`의 **[시스템 프롬프트]**를 system 메시지로, **[사용자 프롬프트]**에 기준일·id·자료를 채워 user 메시지로 보냅니다.
3. 받은 JSON을 `data/<id>.json`으로 저장하고, **사람이 출처와 대조해 검수**합니다.
   - 자료에 없는 사실이 들어갔는지, 수치마다 주체가 붙었는지, 찬반 분량이 비슷한지, stage가 맞는지.

핵심 규칙: 자료에 있는 사실만 · 모르면 비우기 · 찬반 동등 · 수치엔 주장 주체 · 평가어 금지 · JSON만 출력.

## 렌더하기

```bash
cd bill-alert-app/shorts-template
python3 render.py data/elder-care-housing.json --preview   # build/<id>/preview/ 에 장면별 PNG + contact.png
python3 render.py data/elder-care-housing.json             # outputs/<id>_쇼츠.mp4
python3 render.py data/<id>.json --out /원하는/폴더        # 최종 mp4 저장 위치 변경
```

- 필요: Python 3, Pillow, numpy, ffmpeg, Noto Sans CJK(`/usr/share/fonts/opentype/noto/NotoSansCJK-*.ttc`). `jsonschema`가 있으면 스키마 검증도 함께 합니다.
- 전체 렌더 순서: 장면별 mp4(raw 프레임 → libx264) → concat(`-c copy`) → 합성 패드 음악(A–G–F–G 코드, numpy) 추가(`-c:v copy`, AAC) → 최종 mp4.
- 한 편에 약 15초 걸립니다.

## 제한과 오류 메시지

- **글자 맞춤**: 줄마다 실제 픽셀 폭을 재서(`font.getlength`) 넘치면 글자 크기를 2px씩 최소 크기(약 85%)까지 줄입니다.
  그래도 넘치면 렌더하지 않고 `"[hook.title_lines] 줄 1 "…" 이(가) 너무 깁니다 …"`처럼 **필드 이름**을 알려 줍니다.
- **검증**: 필수 필드, stage 0~5, 줄 수(제목 ≤4, 요약 ≤3, 인용 ≤2, 다음 ≤3), 카드 ≤2장, labels/details는 정확히 6칸, 찬반 짝 맞춤.
- **화면 하단 안전 영역**: 내용이 길어 아래로 밀리면(쇼츠 UI에 가려지는 영역) 오류로 멈춥니다.
- 필드별 권장/최대 글자 수는 `prompt.md` 4절 표를 보세요. 대략: 큰 제목 줄당 10자, 요약 13자, 인용 12자, 카드 본문 19~22자.
- 출처 줄은 매체 이름만 두 줄 안에 들어가야 합니다(같은 매체는 한 번만). 기간은 `sources[].date`의 최소~최대 월, 날짜가 없으면 기준일의 월.
- 배경음은 원본을 분석해 같은 구성(코드 진행·음량·페이드)으로 다시 합성한 것이라, 원본 음원과 비트 단위로 같지는 않습니다.
- 원본 mp4는 마지막 1프레임이 빠진 1313프레임, 템플릿 렌더는 장면 길이 합(43.8초)대로 1314프레임입니다. 나머지 프레임은 모두 동일합니다.
