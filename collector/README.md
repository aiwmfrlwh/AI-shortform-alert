# collector — 국회 API 수집기

국회 공식 API로 법안 정보와 제안이유를 가져와 `data/assembly/`에 JSON으로 저장합니다.
GitHub Actions(`Update bills`)가 2시간마다 자동으로 실행하므로 평소에는 손댈 일이 없습니다.

```
cd collector
pip install openpyxl
python fetch_bill.py             # data/assembly/tracked.json 의 법안 전체
python fetch_bill.py 2218220     # 법안 하나만 (주의: bills.json 이 이 법안만으로 바뀜)
```

- 추적할 법안 추가: `data/assembly/tracked.json`에 `{"bill_no": "의안번호", "memo": "메모"}` 추가
- 인증키: `collector/.env` (견본 `.env.example`). 자세한 내용은 `API_사용_가이드.md`
