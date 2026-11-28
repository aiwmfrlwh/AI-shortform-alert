# data/ — 데이터 형식

이 저장소의 데이터는 모두 이 폴더에 있습니다. 형식은 JSON(UTF-8, 들여쓰기 2칸)이고,
사람이 읽는 조사 자료만 Markdown(`sources.md`), 영상과 이미지는 mp4, jpg입니다.
밑줄(`_`)로 시작하는 칸(예: `"_설명"`)은 사람용 메모라서 앱에 실리지 않습니다.

`python3 scripts/build_site.py --check`가 아래 규칙을 검사합니다. 배포 때도 같은 검사를 하고, 틀리면 배포를 멈춥니다.

## bills/<id>/ — 쇼츠가 있는 법안

| 파일 | 내용 | 누가 |
|---|---|---|
| `bill.json` | 앱 카드, 상세 화면, 알림 | 사람 (LLM 초안: `templates/prompt_bill_card.md`) |
| `shorts.json` | 쇼츠 화면 문구. 형식은 `shorts/schema.json` | 사람 (LLM 초안: `shorts/prompt.md`) |
| `sources.md` | 조사 자료. 위 두 파일의 근거 | 사람 |
| `shorts.mp4`, `poster.jpg` | 완성 쇼츠와 썸네일 | `shorts/render.py` |

### bill.json

| 칸 | 형식 | 뜻 |
|---|---|---|
| `id` | 문자 | 폴더 이름과 같아야 함 |
| `draft` | true/false | true면 아직 앱에 싣지 않음 (없으면 false) |
| `short`, `title` | 문자 | 짧은 이름, 공식에 가까운 이름 |
| `cat` | 문자 | 카드에 보이는 분야 |
| `cats` | 목록 | 관심 분야 필터용. `app/categories.json`의 `name` 중에서 |
| `cur` | 0~5 | 지금 단계: 0 접수·발의, 1 소관위 회부, 2 소관위 심사, 3 법사위, 4 본회의, 5 정부 이송·공포 |
| `hold` | true/false | 의결 보류 |
| `tag` | 문자 (생략 가능) | 상태 꼬리표 (계류, 대기 등) |
| `status`, `when` | 문자 | 지금 상태 한 줄, 그 날짜 `MM.DD` |
| `date` | 문자 | 같은 날짜 `YYYY-MM-DD`. 홈의 기간(오늘, 이번 주, 이번 달) 나눠 보기에 씀 |
| `subs` | 6칸 목록 | 단계별 설명 (`cur` 번호 순서) |
| `summary`, `pro`, `con` | 문장 목록 | 쉬운 설명, 찬성 근거, 반대 근거 |
| `notices` | 목록 | 알림 `{"id", "date": "MM.DD", "text"}`. id는 앱 전체에서 겹치지 않게 |
| `sources` | 목록 | 출처 `{"outlet": 매체, "url": 주소}` |

`shorts.json`의 출처는 같은 형식에 `title`, `date`가 더 붙습니다(`{"outlet", "title", "url", "date"}`).

## app/ — 앱 공통

| 파일 | 형식 |
|---|---|
| `settings.json` | `bill_order`(앱에 보이는 법안 순서, 없는 법안은 뒤에 붙음), `welcome_bill`(첫 화면 예시), `default_follow`, `default_interests`(처음 온 사람 기본값) |
| `categories.json` | `[{"name": "주거·부동산", "keywords": ["주택", ...]}]`. 국회 새 법안을 이름의 키워드로 분야에 나눔 |
| `search.json` | `{"suggest": [추천 검색어], "synonyms": {"킥보드": ["개인형 이동장치", ...]}}` |
| `terms.json` | `{"groups": [분류 이름], "flow": [{"label", "term"}], "terms": [{"term", "group": 분류 번호, "aliases", "desc", "law", "example": 법안 id}]}` |
| `popular.json` | `[{"id", "likes", "saves", "requests"}]`. 여러 사람의 공감 수를 모을 서버가 생기면 채움 |

## assembly/ — 국회 API 자동 수집

`collector/fetch_bill.py`가 2시간마다(GitHub Actions `Update bills`) 이 폴더를 갱신합니다.

| 파일 | 누가 | 내용 |
|---|---|---|
| `tracked.json` | 사람 | 추적할 법안 `[{"bill_no": "2218220", "memo": "메모"}]` |
| `bill_texts.json` | 사람 | API가 원문을 못 줄 때 쓰는 제안이유 수동 입력. 키는 의안번호 |
| `bills.json` | 자동 | 추적 법안의 진행 상황. 칸 설명은 `collector/API_사용_가이드.md` 5절 |
| `new_bills.json` | 자동 | 새로 발의된 법안 (최근이 맨 앞, 최대 500건) |
| `changes.json` | 자동 | 진행 상황이 바뀐 기록 (최근이 맨 앞) |
| `raw/<의안번호>.json` | 자동 | API 원본 응답 (확인용) |
| `exports/bills.csv`, `exports/bills.xlsx` | 자동 | `bills.json`을 엑셀로 보기 위한 사본 (고쳐도 반영되지 않음) |
