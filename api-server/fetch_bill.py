"""
국회 법안 정보 조회 스크립트 (AI즐기조)

사용법 (PowerShell에서):
    python fetch_bill.py 2218220
    python fetch_bill.py 2218220 2223257      <- 여러 개도 가능

결과물 (output 폴더):
    bills.csv / bills.xlsx / bills.json  : 팀 공통 데이터
    raw_<의안번호>.json                 : API가 보내준 원본 응답 (확인용)

인증키: 같은 폴더의 .env 파일에 ASSEMBLY_API_KEY=키 를 적어 두면 자동으로 읽는다.
       키가 없으면 '샘플 모드'(최대 10건)로 호출된다. 법안 한두 건 조회에는 샘플 모드로도 충분하다.
"""
import csv
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "output"
API_URL = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"  # 국회의원 발의법률안
SUMMARY_URL = "https://open.assembly.go.kr/portal/openapi/BPMBILLSUMMARY"  # 법률안 제안이유 및 주요내용
SUBCMT_URL = "https://open.assembly.go.kr/portal/openapi/TVBPMCONFINFO"  # 소위 심사정보(법률안)
AGE = "22"  # 제22대 국회
SOURCE_URL = "https://open.assembly.go.kr/portal/openapi/main.do"

COLUMNS = [
    "bill_id", "bill_name", "proposer", "propose_date", "committee",
    "status", "status_date", "stage_no",
    "committee_referred_date", "committee_present_date",
    "subcommittee_name", "subcommittee_referred_date", "subcommittee_present_date",
    "subcommittee_proc_date", "subcommittee_result",
    "proposal_reason", "main_content", "note", "text_source",
    "original_url", "source_url", "last_checked", "api_status",
]

# 화면 표시용 진행 단계 (팀원 A용). stage_no 는 이 목록의 순서(1부터), 0은 진행 종료(폐기, 철회, 부결).
STAGES = ["발의", "위원회 회부", "위원회 상정", "법안소위 심사", "위원회 의결",
          "법사위 심사", "본회의 의결", "정부 이송", "공포"]


def load_key():
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ASSEMBLY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def call_api(bill_no, key, url=API_URL, extra=None):
    params = {"Type": "json", "pIndex": 1, "pSize": 10, "BILL_NO": bill_no, **(extra or {})}
    if key:
        params["KEY"] = key
    else:
        params["pSize"] = 5  # 샘플 모드 제한
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_summary(bill_no, key):
    """제안이유/주요내용/참고사항을 공식 API에서 가져와 나눈다. 실패하면 None."""
    try:
        code, _, rows = parse(call_api(bill_no, key, SUMMARY_URL), "BPMBILLSUMMARY")
    except Exception:
        return None
    if code != "INFO-000" or not rows or not rows[0].get("SUMMARY"):
        return None
    sections, current = {}, "본문"
    for line in rows[0]["SUMMARY"].splitlines():
        line = line.strip()
        if line in ("제안이유", "주요내용", "참고사항", "제안이유 및 주요내용"):
            current = line
            continue
        if line:
            sections.setdefault(current, []).append(line)
    get = lambda k: "\n".join(sections.get(k, []))
    reason = get("제안이유")
    content = get("주요내용")
    if not reason and not content:  # 제목 구분 없이 한 덩어리인 법안
        reason = get("제안이유 및 주요내용") or get("본문")
        content = "(원문에서 제안이유와 구분되어 있지 않음. proposal_reason 참고)"
    return {"proposal_reason": reason, "main_content": content, "note": get("참고사항")}


def fetch_subcommittee(bill_no, key):
    """법안소위 회부일/상정일/처리일을 공식 API에서 가져온다. 소위에 안 갔거나 실패하면 None."""
    try:
        code, _, rows = parse(call_api(bill_no, key, SUBCMT_URL, {"AGE": AGE}), "TVBPMCONFINFO")
    except Exception:
        return None
    if code != "INFO-000" or not rows:
        return None
    # 한 법안에 여러 줄이 올 수 있다(재회부, 안건조정위원회 등).
    # 회부일은 있는 값 중 가장 늦은 것, 나머지는 가장 최근에 움직인 줄에서 가져온다.
    dates = lambda x: max(x.get("SUBMIT_DT") or "", x.get("PRESENT_DT") or "", x.get("PROC_DT") or "")
    r = max(rows, key=lambda x: (dates(x), bool(x.get("PROC_DT")), "소위" in (x.get("SUB_COMMITTEE_NAME") or "")))
    return {
        "subcommittee_name": r.get("SUB_COMMITTEE_NAME") or "",
        "subcommittee_referred_date": max((x.get("SUBMIT_DT") or "" for x in rows), default=""),
        "subcommittee_present_date": r.get("PRESENT_DT") or "",
        "subcommittee_proc_date": r.get("PROC_DT") or "",
        "subcommittee_result": r.get("PROC_RESULT_CD") or "",
    }


def parse(raw, name="nzmimeepazxkubdpn"):
    """응답에서 결과코드와 법안 목록을 꺼낸다."""
    if "RESULT" in raw:  # 데이터 없음, 키 오류 등
        return raw["RESULT"]["CODE"], raw["RESULT"]["MESSAGE"], []
    body = raw[name]
    result = body[0]["head"][1]["RESULT"]
    rows = body[1]["row"] if len(body) > 1 else []
    return result["CODE"], result["MESSAGE"], rows


def derive_status(r, sub):
    """API 날짜 항목을 보고 가장 마지막에 진행된 단계를 고른다.
    폐기, 철회, 부결처럼 더 진행되지 않는 법안은 stage_no 0(진행 종료)으로 둔다."""
    result = r.get("PROC_RESULT") or ""
    if r.get("PROC_DT") and any(w in result for w in ("폐기", "철회", "부결")):
        return f"진행 종료: {result}", r["PROC_DT"], 0
    checks = [
        ("PROC_DT", f"본회의 {r.get('PROC_RESULT') or '의결'}", 7),
        ("LAW_PROC_DT", "법사위 심사 완료", 6),
        ("LAW_PRESENT_DT", "법사위 상정", 6),
        ("LAW_SUBMIT_DT", "법사위 회부", 6),
        ("CMT_PROC_DT", f"위원회 {r.get('CMT_PROC_RESULT_CD') or '처리'}", 5),
    ]
    for field, label, stage in checks:
        if r.get(field):
            return label, r[field], stage
    if sub.get("subcommittee_proc_date"):
        return f"법안소위 {sub.get('subcommittee_result') or '처리'}", sub["subcommittee_proc_date"], 4
    if sub.get("subcommittee_present_date"):
        return "법안소위 상정", sub["subcommittee_present_date"], 4
    if sub.get("subcommittee_referred_date"):
        return "법안소위 심사 중", sub["subcommittee_referred_date"], 4
    if r.get("CMT_PRESENT_DT"):
        return "위원회 상정", r["CMT_PRESENT_DT"], 3
    if r.get("COMMITTEE_DT"):
        return "위원회 회부", r["COMMITTEE_DT"], 2
    return "발의(접수)", r.get("PROPOSE_DT"), 1


def to_record(r, texts, api_status, summary, sub):
    t = texts.get(r["BILL_NO"], {})
    if not sub:  # API에 없으면 data/bill_texts.json 수동 입력값 사용
        sub = {"subcommittee_referred_date": t.get("subcommittee_referred_date", "")}
    sub = {k: sub.get(k, "") for k in ("subcommittee_name", "subcommittee_referred_date",
                                       "subcommittee_present_date", "subcommittee_proc_date",
                                       "subcommittee_result")}
    status, status_date, stage = derive_status(r, sub)
    if summary:  # 1순위: 공식 API 자동 수집
        reason, content, note = summary["proposal_reason"], summary["main_content"], summary["note"]
        text_source = "API 자동(BPMBILLSUMMARY)"
    elif t.get("proposal_reason"):  # 2순위: data/bill_texts.json 수동 입력
        reason, content, note = t["proposal_reason"], "\n".join(t.get("main_content", [])), t.get("note", "")
        text_source = f"수동 입력({t.get('checked_date', '')})"
    else:
        reason = content = "미확인(원문 없음)"
        note, text_source = "", "없음"
    return {
        "bill_id": r["BILL_NO"],
        "bill_name": r["BILL_NAME"],
        "proposer": r["PROPOSER"],
        "propose_date": r["PROPOSE_DT"],
        "committee": r.get("COMMITTEE") or "",
        "status": status,
        "status_date": status_date or "",
        "stage_no": stage,
        "committee_referred_date": r.get("COMMITTEE_DT") or "",
        "committee_present_date": r.get("CMT_PRESENT_DT") or "",
        **sub,
        "proposal_reason": reason,
        "main_content": content,
        "note": note,
        "text_source": text_source,
        "original_url": r["DETAIL_LINK"].replace("http://", "https://"),
        "source_url": SOURCE_URL,
        "last_checked": date.today().isoformat(),
        "api_status": api_status,
    }


def save(records):
    OUT.mkdir(exist_ok=True)
    (OUT / "bills.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "bills.csv", "w", newline="", encoding="utf-8-sig") as f:  # 엑셀에서 한글 안 깨지게
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(records)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("  (엑셀 파일을 만들려면: pip install openpyxl)")
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "bills"
    ws.append(COLUMNS)
    for rec in records:
        ws.append([rec[c] for c in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    wide = {"bill_name": 32, "proposal_reason": 60, "main_content": 60, "note": 40,
            "original_url": 40, "source_url": 30, "api_status": 24, "text_source": 20,
            "subcommittee_name": 24}
    for i, name in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = wide.get(name, 12)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    wb.save(OUT / "bills.xlsx")


def main():
    bill_nos = sys.argv[1:] or ["2218220"]
    key = load_key()
    mode = "인증키 사용" if key else "샘플 모드(인증키 없음)"
    print(f"호출 방식: {mode}")
    texts_file = BASE / "data" / "bill_texts.json"
    texts = json.loads(texts_file.read_text(encoding="utf-8")) if texts_file.exists() else {}

    OUT.mkdir(exist_ok=True)
    records = []
    for no in bill_nos:
        try:
            raw = call_api(no, key, extra={"AGE": AGE})
        except Exception as e:
            print(f"[{no}] 연결 실패: {e}")
            continue
        (OUT / f"raw_{no}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        code, msg, rows = parse(raw)
        if code != "INFO-000" or not rows:
            print(f"[{no}] 결과 없음: {code} {msg}")
            continue
        api_status = f"API 호출 성공 {date.today().isoformat()} ({mode})"
        summary = fetch_summary(no, key)
        sub = fetch_subcommittee(no, key)
        for r in rows:
            rec = to_record(r, texts, api_status, summary, sub)
            records.append(rec)
            print(f"[{no}] {rec['bill_name']} / {rec['proposer']} / {rec['status']} ({rec['status_date']})"
                  f" / 원문: {rec['text_source']}")

    if records:
        save(records)
        print(f"저장 완료: {OUT}")


if __name__ == "__main__":
    main()
