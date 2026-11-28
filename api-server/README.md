# api-server

국회 공식 API로 법안 정보와 제안이유를 가져와 엑셀, CSV, JSON으로 저장합니다.

```
pip install openpyxl
python fetch_bill.py 2218220
```

결과는 output 폴더에 생깁니다. 인증키 설정은 API_사용_가이드.md를 보세요.

자동 업데이트 때 함께 저장되는 것 (2026-11-28 추가)
- `output/bills.json`, `output/new_bills.json`: 법안마다 대표발의 의원(`lead_proposer`, `lead_mona`), 공동발의 의원(`co_proposers`, `co_mona`), 공동발의자 명단 링크(`member_list_url`)
- `output/members.json`: 현직 국회의원 명단(정당, 지역구, 선수, 소속 위원회). 국회의원 인적사항 API로 하루 한 번, 인증키가 있을 때만 받음. 웹앱 법안 상세의 "자세히 보기"가 의원코드로 이어 붙여 보여줌
- 첫 실행 뒤 `output/raw_members_sample.json`에서 API 칸 이름(HG_NM, POLY_NM, ORIG_NM, REELE_GBN_NM, CMITS 등)이 맞는지 확인
