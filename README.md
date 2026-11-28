# 법안톡: 국회 입법 알림과 관심 분야 법안 쇼츠

바른정책아카데미 AI 팀 프로젝트입니다.
국회 법안의 진행 단계(발의 > 소관위 > 법사위 > 본회의 > 공포)가 바뀔 때 알림을 받고,
관심 분야 법안을 1분 안팎의 세로 쇼츠로 쉽게 이해하도록 돕는 모바일 웹앱을 만듭니다.

- 배포 주소: https://aiwmfrlwh.github.io/AI-shortform-alert/
- 법안 데이터: 국회 공식 Open API (2시간마다 자동 업데이트)

## 폴더 구성

| 폴더 | 내용 | 안내 |
| --- | --- | --- |
| `bill-alert-app/` | 실제 앱. 웹앱(`web/`), 화면 디자인(`design/`), 완성 쇼츠(`shorts/`), 쇼츠 템플릿(`shorts-template/`) | [README](bill-alert-app/README.md) |
| `api-server/` | 국회 API 수집기 `fetch_bill.py`와 결과(`output/`). 추적 법안 목록은 `bills.txt` | [README](api-server/README.md), [API 사용 가이드](api-server/API_사용_가이드.md) |
| `workspace/` | 팀 작업 문서. 새 법안 쇼츠에 필요한 자료 규격 | [법안 쇼츠 데이터 규격](workspace/법안_쇼츠_데이터_규격.md) |
| `restructure/` | 저장 구조 통일 제안(정리안). 아직 실제 앱, 배포, 자동 업데이트에는 쓰이지 않음 | [README](restructure/README.md) |
| `.github/workflows/` | 자동화. `update-bills.yml`(법안 자동 업데이트), `pages.yml`(웹앱 배포) | 아래 "자동화" 참고 |

## 전체 흐름

```
국회 Open API
   │  api-server/fetch_bill.py (2시간마다, GitHub Actions)
   ▼
api-server/output/  bills.json, new_bills.json, members.json
   │  pages.yml 이 배포 때 web/data/ 로 복사
   ▼
bill-alert-app/web/ (GitHub Pages)  <──  쇼츠 영상 (shorts-template/render.py)
```

쇼츠 1편 만들기: 기사와 법안 자료 정리(`<id>.sources.md`) > LLM 프롬프트로 쇼츠 JSON 생성 > 사람 검수 > `render.py`로 mp4 렌더 > 웹앱에 등록.
자세한 순서는 [법안 쇼츠 데이터 규격](workspace/법안_쇼츠_데이터_규격.md)과 [쇼츠 템플릿 README](bill-alert-app/shorts-template/README.md)를 보세요.

## 시작하기

### 1. 국회 API 인증키 설정
```powershell
cd api-server
copy .env.example .env   # = 뒤에 발급받은 키 입력
```
`.env`는 커밋하거나 메신저에 올리지 않습니다. 키가 없으면 샘플 모드로 동작합니다.

### 2. 법안 데이터 받기
```powershell
pip install openpyxl
python api-server/fetch_bill.py 2218220
```

### 3. 웹앱 로컬에서 보기
```powershell
cd bill-alert-app/web; python -m http.server 8000
```
브라우저에서 http://localhost:8000 을 엽니다.

### 4. 쇼츠 렌더
```powershell
pip install pillow
cd bill-alert-app/shorts-template; python render.py data/pm-law.json
```
Noto Sans CJK 글꼴과 ffmpeg가 필요합니다.

## 자동화

- **Update bills** (`update-bills.yml`): 2시간마다 국회 API를 확인해 새 법안이나 추적 법안 상태가 바뀌었을 때만 `api-server/output/`을 커밋합니다. 저장소 Secrets의 `ASSEMBLY_API_KEY`를 씁니다.
- **Deploy web app** (`pages.yml`): `main`의 웹앱이나 법안 데이터가 바뀌면, 또는 Update bills가 끝나면 GitHub Pages로 배포합니다.

두 작업 모두 Actions 탭의 "Run workflow"로 직접 실행할 수 있습니다.

## 작업 규칙

- 쇼츠 화면 문구에는 단어 사이 가운뎃점을 쓰지 않습니다. 나열은 쉼표나 "와/과"로 씁니다. (`render.py`가 검사)
- 쇼츠 문구는 자료에 있는 사실만 쓰고, 찬반을 같은 분량으로 다루며, 수치에는 주장한 주체를 붙입니다.
- 법안 id는 영문 소문자, 숫자, 하이픈만 씁니다. (예: `otc-law`)
- `api-server/output/`의 결과 파일은 자동 수집기가 고칩니다. 손으로 고치지 않습니다.

## 완성 쇼츠 (2026-11-28 기준)

건보공단 특사경법, 고령자돌봄주택법, PM법, 편의점 상비약법, 개인정보 보호법 개정안
(`bill-alert-app/shorts/`)
