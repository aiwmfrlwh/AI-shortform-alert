# 법안톡 — 국회 입법 알림 & 관심 분야 쇼츠 앱

국회 법안의 진행 단계(발의 → 소관위 → 법사위 → 본회의 → 공포)를 알림으로 받고,
관심 분야 법안을 60초 쇼츠로 보는 앱 프로젝트입니다.

## 구성
- `design/` — 앱 화면 디자인 (관심 분야 선택, 홈, 법안 상세, 쇼츠, 알림 설정). Claude Design 캔버스 원본 파일
- `shorts/make_shorts.py` — 법안 요약 쇼츠(1080×1920, 30fps) 생성 스크립트 (Python + Pillow + ffmpeg)
- `shorts/건보특사경법_쇼츠.mp4` — 예시 쇼츠: 건보공단 특사경법 (2026.11.26 기준)

## 쇼츠 다시 만들기
```bash
pip install pillow
python3 shorts/make_shorts.py preview   # 미리보기 프레임
python3 shorts/make_shorts.py all       # 장면별 mp4 렌더링
```
Noto Sans CJK 글꼴과 ffmpeg가 필요합니다.
