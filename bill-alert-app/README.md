# 법안톡 — 국회 입법 알림 & 관심 분야 쇼츠 앱

국회 법안의 진행 단계(발의 → 소관위 → 법사위 → 본회의 → 공포)를 알림으로 받고,
관심 분야 법안을 60초 쇼츠로 보는 앱 프로젝트입니다.

## 구성
- `web/` — 실제로 동작하는 모바일 웹앱 (HTML 한 파일 + 예시 쇼츠 영상). 관심 분야 선택, 법안 진행 단계, 팔로우·알림 설정, 쇼츠 재생이 동작하며 선택 내용은 브라우저에 저장됩니다
- `design/` — 앱 화면 디자인 (관심 분야 선택, 홈, 법안 상세, 쇼츠, 알림 설정). Claude Design 캔버스 원본 파일
- `shorts/make_shorts.py` — 법안 요약 쇼츠(1080×1920, 30fps) 생성 스크립트 (Python + Pillow + ffmpeg)
- `shorts/*.mp4` — 완성 쇼츠: 건보공단 특사경법, 고령자돌봄주택법, PM법, 편의점 상비약법 (2026.11.26 기준)
- `shorts-template/` — 법안 문구를 JSON으로 넣으면 같은 디자인의 쇼츠가 나오는 템플릿과 LLM 프롬프트 (화면 문구에 중간점 금지)

## 쇼츠 다시 만들기
```bash
pip install pillow
python3 shorts/make_shorts.py preview   # 미리보기 프레임
python3 shorts/make_shorts.py all       # 장면별 mp4 렌더링
```
Noto Sans CJK 글꼴과 ffmpeg가 필요합니다.

## 웹앱 배포 (GitHub Pages)
`main`에 `bill-alert-app/web/`이 바뀌면 `.github/workflows/pages.yml`이 자동으로 배포합니다.
처음 한 번만 저장소 **Settings → Pages → Source**를 **GitHub Actions**로 바꿔 주세요.
배포 주소: https://aiwmfrlwh.github.io/AI-shortform-alert/

로컬에서 보기:
```bash
cd bill-alert-app/web && python3 -m http.server 8000
# http://localhost:8000
```
법안 데이터는 2026년 11월 보도를 바탕으로 정리한 시연용 데이터입니다 (`index.html`의 `BILLS`).
