# 법안톡 — 국회 입법 알림 & 관심 분야 쇼츠 앱

국회 법안의 진행 단계(발의 → 소관위 → 법사위 → 본회의 → 공포)를 알림으로 받고,
관심 분야 법안을 1분 쇼츠로 보는 앱 프로젝트입니다.

- 배포 주소: https://aiwmfrlwh.github.io/AI-shortform-alert/
- 새 법안 추가하기: [docs/새_법안_추가하기.md](docs/새_법안_추가하기.md)
- 데이터 형식: [data/README.md](data/README.md)

## 저장 규칙 (이것만 기억하기)

1. **데이터는 전부 `data/` 한 곳에, JSON으로.** 코드 폴더(`web/`, `shorts/`, `collector/`)에는 데이터를 두지 않습니다.
2. **법안 하나 = 폴더 하나.** `data/bills/<id>/`에 그 법안의 앱 카드, 쇼츠 문구, 조사 자료, 영상, 썸네일이 모두 있습니다.
3. **같은 내용은 한 번만 저장합니다.** 배포용 복사본은 `scripts/build_site.py`가 그때그때 만들고(`_site/`, 커밋 안 함), 엑셀/CSV는 JSON의 사본입니다.
4. **사람이 고치는 파일과 프로그램이 고치는 파일을 나눕니다.** `data/assembly/`의 결과 파일은 자동 수집기만 고칩니다.
5. **id는 영문 소문자, 숫자, 하이픈** (예: `otc-law`). 폴더 이름 = `bill.json`의 id = `shorts.json`의 id.

## 폴더 지도

```
AI-shortform-alert/
├── data/                        모든 데이터 (JSON)
│   ├── bills/<id>/              쇼츠가 있는 법안 (사람이 작성)
│   │   ├── bill.json            앱 카드, 상세 화면, 알림 내용
│   │   ├── shorts.json          쇼츠 화면 문구
│   │   ├── sources.md           조사 자료 (bill.json, shorts.json 의 근거)
│   │   ├── shorts.mp4           완성 쇼츠 (shorts/render.py 가 만듦)
│   │   └── poster.jpg           썸네일 (shorts/render.py 가 만듦)
│   ├── app/                     앱 공통 데이터 (사람이 작성)
│   │   ├── settings.json        법안 순서, 첫 화면 법안, 처음 사용자 기본값
│   │   ├── categories.json      관심 분야 16개와 자동 분류 키워드
│   │   ├── search.json          추천 검색어, 생활 단어 → 법안 단어
│   │   ├── terms.json           용어 사전
│   │   └── popular.json         인기 순위 (서버가 생기면 채움, 지금은 빈 목록)
│   └── assembly/                국회 API 자동 수집 (2시간마다)
│       ├── tracked.json         추적할 의안번호 (사람이 작성)
│       ├── bill_texts.json      API에 없는 원문 수동 입력 (사람이 작성)
│       ├── bills.json           추적 법안 진행 상황 (자동)
│       ├── new_bills.json       새로 발의된 법안 (자동)
│       ├── changes.json         진행 상황 변경 기록 (자동)
│       ├── raw/<의안번호>.json   API 원본 응답 (자동)
│       └── exports/             bills.csv, bills.xlsx (자동, bills.json 의 엑셀용 사본)
├── web/                         웹앱 코드 (index.html 한 파일, 데이터 없음)
├── shorts/                      쇼츠 렌더러 render.py, 스키마, LLM 프롬프트
├── collector/                   국회 API 수집기 fetch_bill.py, API 사용 가이드
├── design/                      앱 화면 디자인 원본 (Claude Design 캔버스)
├── templates/                   새 법안 템플릿
│   ├── bill/                    bill.json, shorts.json, sources.md 빈 양식
│   └── prompt_bill_card.md      bill.json 을 만드는 LLM 프롬프트
├── scripts/
│   ├── new_bill.py              새 법안 폴더 만들기
│   └── build_site.py            데이터 검사 + 배포 폴더(_site/) 만들기 + 미리보기
├── docs/
│   ├── 새_법안_추가하기.md        처음부터 끝까지 작업 순서
│   └── 법안_쇼츠_데이터_규격.md    데이터 담당자가 넘길 자료와 쇼츠 JSON 필드 규격
└── .github/workflows/
    ├── update-bills.yml         2시간마다 국회 API 확인 → data/assembly/ 갱신
    └── pages.yml                data/ 나 web/ 이 바뀌면 검사 후 GitHub Pages 배포
```

브라우저 안에서만 저장되는 것(관심 분야, 팔로우, 공감, 저장, 알림 설정)은 각 사용자 브라우저의 localStorage에 있고 저장소에는 없습니다.

## 자주 쓰는 명령 (저장소 맨 위 폴더에서)

```bash
python3 scripts/new_bill.py <id> --bill-no <의안번호>        # 새 법안 폴더
python3 shorts/render.py data/bills/<id>/shorts.json --preview  # 쇼츠 미리보기
python3 shorts/render.py data/bills/<id>/shorts.json            # 쇼츠 영상 + 썸네일
python3 scripts/build_site.py --check                          # 데이터 검사만
python3 scripts/build_site.py --serve                          # http://localhost:8000 에서 앱 보기
```

필요한 것: Python 3. 쇼츠 렌더에는 Pillow, numpy, ffmpeg, Noto Sans CJK 글꼴. 수집기 엑셀 사본에는 openpyxl.

## 배포

`main`에 `web/`이나 `data/`가 바뀌면 `pages.yml`이 `scripts/build_site.py`로 데이터를 검사하고 `_site/`를 만들어 GitHub Pages에 올립니다.
검사에서 오류가 나면 배포되지 않고 Actions 탭에 어떤 파일의 어떤 칸이 문제인지 나옵니다.
처음 한 번만 저장소 **Settings → Pages → Source**를 **GitHub Actions**로 바꿔 주세요.

쇼츠 법안 4건의 내용은 2026년 11월 보도를 바탕으로 정리한 시연용 데이터입니다.
