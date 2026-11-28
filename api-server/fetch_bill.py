"""
국회 법안 정보 조회 스크립트 (AI즐기조)

사용법 (PowerShell에서):
    python fetch_bill.py 2218220
    python fetch_bill.py 2218220 2223257      <- 여러 개도 가능
    python fetch_bill.py                      <- bills.txt 에 적힌 법안 전체 (자동 업데이트가 쓰는 방식)

결과물 (output 폴더):
    bills.csv / bills.xlsx / bills.json  : 팀 공통 데이터
    changes.json                        : 진행 상황이 바뀐 기록 (알림용)
    new_bills.json                      : 새로 발의된 법안 목록 (bills.txt 로 실행할 때만)

인증키 횟수 절약: 끝난 법안은 조회하지 않고, 제안이유는 한 번만 받고, 소위 정보는 위원회 심사 중일 때만 받는다.
바뀐 게 없으면 파일을 고치지 않는다.
    raw_<의안번호>.json                 : API가 보내준 원본 응답 (확인용)

인증키: 같은 폴더의 .env 파일에 ASSEMBLY_API_KEY=키 를 적어 두면 자동으로 읽는다.
       키가 없으면 '샘플 모드'(최대 10건)로 호출된다. 법안 한두 건 조회에는 샘플 모드로도 충분하다.
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

BASE = Path(__file__).parent
OUT = BASE / "output"
API_URL = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"  # 국회의원 발의법률안
SUMMARY_URL = "https://open.assembly.go.kr/portal/openapi/BPMBILLSUMMARY"  # 법률안 제안이유 및 주요내용
SUBCMT_URL = "https://open.assembly.go.kr/portal/openapi/TVBPMCONFINFO"  # 소위 심사정보(법률안)
MEMBER_URL = "https://open.assembly.go.kr/portal/openapi/nwvrqwxyaytdsfvhu"  # 국회의원 인적사항
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
    if os.environ.get("ASSEMBLY_API_KEY"):  # GitHub Actions 등에서 환경변수로 넣은 경우
        return os.environ["ASSEMBLY_API_KEY"].strip()
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("ASSEMBLY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


CALLS = {"n": 0}  # 이번 실행에서 API를 몇 번 불렀는지 (인증키 사용량 확인용)


def call_api(bill_no, key, url=API_URL, extra=None):
    CALLS["n"] += 1
    params = {"Type": "json", "pIndex": 1, "pSize": 10, **(extra or {})}
    if bill_no:
        params["BILL_NO"] = bill_no
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


def proposer_fields(r):
    """대표발의 의원, 공동발의 의원 이름과 의원코드(MONA_CD). 의원 정보(members.json)와 이어 붙일 때 쓴다."""
    split = lambda v: [x.strip() for x in (v or "").split(",") if x.strip()]
    return {
        "lead_proposer": r.get("RST_PROPOSER") or "",
        "lead_mona": r.get("RST_MONA_CD") or "",
        "co_proposers": split(r.get("PUBL_PROPOSER")),
        "co_mona": split(r.get("PUBL_MONA_CD")),
        "member_list_url": (r.get("MEMBER_LIST") or "").replace("http://", "https://"),
    }


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
        "last_checked": today(),
        "api_status": api_status,
        **proposer_fields(r),
    }


def save(records):
    OUT.mkdir(exist_ok=True)
    (OUT / "bills.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / "bills.csv", "w", newline="", encoding="utf-8-sig") as f:  # 엑셀에서 한글 안 깨지게
        w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")  # 의원 목록 같은 칸은 엑셀 사본에서 뺌
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


def today():
    return datetime.now(KST).date().isoformat()  # 서버(GitHub)가 외국 시간이어도 한국 날짜로 기록


def read_bill_list():
    """bills.txt 에서 의안번호를 읽는다. # 뒤는 메모로 무시."""
    path = BASE / "bills.txt"
    if not path.exists():
        return []
    nos = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            nos.append(line)
    return nos


def record_changes(old_records, new_records):
    """이전 결과와 비교해 진행 상황이 바뀐 법안을 changes.json 맨 앞에 추가한다."""
    old = {r["bill_id"]: r for r in old_records}
    found = []
    for r in new_records:
        before = old.get(r["bill_id"])
        if before and (before["status"], before["status_date"]) != (r["status"], r["status_date"]):
            found.append({
                "detected_date": today(),
                "bill_id": r["bill_id"],
                "bill_name": r["bill_name"],
                "before": f"{before['status']} ({before['status_date']})",
                "after": f"{r['status']} ({r['status_date']})",
                "stage_no": r["stage_no"],
                "original_url": r["original_url"],
            })
    path = OUT / "changes.json"
    history = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    path.write_text(json.dumps(found + history, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in found:
        print(f"[변경] {c['bill_id']} {c['bill_name']}: {c['before']} -> {c['after']}")
    return found


SUB_FIELDS = ("subcommittee_name", "subcommittee_referred_date", "subcommittee_present_date",
              "subcommittee_proc_date", "subcommittee_result")
IGNORE_IN_COMPARE = ("last_checked", "api_status")  # 이 두 칸만 바뀐 건 '변경'으로 보지 않음


def detect_new_bills(key):
    """최근 발의 법안 목록을 API 1번으로 받아, 처음 보는 법안을 new_bills.json 맨 앞에 추가한다."""
    try:
        code, msg, rows = parse(call_api("", key, extra={"AGE": AGE, "pSize": 100}))
    except Exception as e:
        print(f"[새 법안 확인] 연결 실패: {e}")
        return False
    if code != "INFO-000":
        print(f"[새 법안 확인] 결과 없음: {code} {msg}")
        return False
    path = OUT / "new_bills.json"
    first_run = not path.exists()
    known = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    seen = {b["bill_id"] for b in known}
    fresh = [{
        "detected_date": today(),
        "bill_id": r["BILL_NO"],
        "bill_name": r["BILL_NAME"],
        "proposer": r["PROPOSER"],
        "propose_date": r["PROPOSE_DT"],
        "original_url": r["DETAIL_LINK"].replace("http://", "https://"),
        "committee": r.get("COMMITTEE") or "",
        **proposer_fields(r),
    } for r in rows if r["BILL_NO"] not in seen]
    # 예전에 받은 법안에 의원 정보 칸이 없으면, 이번 응답에 같은 법안이 있을 때 채운다 (API 추가 호출 없음)
    by_no = {r["BILL_NO"]: r for r in rows}
    filled = 0
    for b in known:
        r = by_no.get(b["bill_id"])
        if r and "lead_proposer" not in b:
            b.update({"committee": r.get("COMMITTEE") or "", **proposer_fields(r)})
            filled += 1
    if not fresh and not filled:
        print("[새 법안 확인] 새로 발의된 법안 없음")
        return False
    if filled:
        print(f"[새 법안 확인] 기존 법안 {filled}건에 발의 의원 정보를 채웠습니다")
    path.write_text(json.dumps((fresh + known)[:500], ensure_ascii=False, indent=2), encoding="utf-8")
    if first_run:
        print(f"[새 법안 확인] 처음 실행이라 최근 법안 {len(fresh)}건으로 기준 목록을 만들었습니다")
    else:
        for b in fresh:
            print(f"[새 법안] {b['bill_id']} {b['bill_name']} ({b['proposer']}, {b['propose_date']})")
    return True


def update_members(key):
    """현직 국회의원 명단(정당, 지역구, 선수, 소속 위원회)을 하루 한 번 받아 members.json 에 저장한다.
    의원코드(MONA_CD)를 키로 써서, 법안의 대표발의, 공동발의 의원과 이어 붙인다. 인증키가 있어야 전체 명단을 받는다."""
    path = OUT / "members.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if old.get("updated") == today():
        print("[의원 명단] 오늘 이미 받음 - 생략")
        return
    if not key:
        print("[의원 명단] 인증키가 없어 생략 (샘플 모드는 5명까지만 줌)")
        return
    rows, page = [], 1
    try:
        while page <= 5:
            params = {"Type": "json", "pIndex": page, "pSize": 300, "KEY": key}
            req = urllib.request.Request(MEMBER_URL + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "Mozilla/5.0"})
            CALLS["n"] += 1
            with urllib.request.urlopen(req, timeout=30) as r:
                code, msg, got = parse(json.loads(r.read().decode("utf-8")), "nwvrqwxyaytdsfvhu")
            if code != "INFO-000":
                print(f"[의원 명단] 결과 없음: {code} {msg}")
                break
            rows += got
            if len(got) < 300:
                break
            page += 1
    except Exception as e:
        print(f"[의원 명단] 연결 실패: {e} - 이전 명단 유지")
        return
    if not rows:
        return
    (OUT / "raw_members_sample.json").write_text(json.dumps(rows[:2], ensure_ascii=False, indent=2), encoding="utf-8")
    members = {}
    for m in rows:
        code = m.get("MONA_CD")
        if not code:
            continue
        members[code] = {
            "name": m.get("HG_NM") or "",
            "party": m.get("POLY_NM") or "",
            "district": m.get("ORIG_NM") or "",
            "elect_type": m.get("ELECT_GBN_NM") or "",
            "terms": m.get("REELE_GBN_NM") or "",
            "units": m.get("UNITS") or "",
            "committee": m.get("CMIT_NM") or "",
            "committees": m.get("CMITS") or "",
            "homepage": m.get("HOMEPAGE") or "",
        }
    if members == old.get("members"):
        old["updated"] = today()
        path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[의원 명단] 바뀐 것 없음 ({len(members)}명)")
        return
    path.write_text(json.dumps({"updated": today(), "source": MEMBER_URL, "members": members}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[의원 명단] {len(members)}명 저장")


def update_bill(no, prev, key, texts, mode):
    """법안 하나를 갱신한다. 꼭 필요한 API만 부른다. 실패하면 이전 값을 돌려준다."""
    if prev and prev["stage_no"] in (0, 9):  # 폐기/철회/부결 또는 공포: 더 바뀌지 않음
        print(f"[{no}] {prev['status']} - 끝난 법안이라 조회 생략")
        return prev
    try:
        raw = call_api(no, key, extra={"AGE": AGE})
        code, msg, rows = parse(raw)
    except Exception as e:
        code, msg, rows, raw = "연결 실패", str(e), [], None
    if code != "INFO-000" or not rows:
        print(f"[{no}] 결과 없음: {code} {msg}")
        if prev:  # 일시적인 오류로 기존 데이터가 사라지지 않게 이전 값 유지
            print(f"[{no}] 이전 데이터를 그대로 유지합니다 (마지막 확인 {prev['last_checked']})")
        return prev
    r = rows[0]

    # 제안이유는 한 번 받으면 바뀌지 않으므로 재사용
    if prev and prev.get("text_source", "").startswith("API"):
        summary = {k: prev[k] for k in ("proposal_reason", "main_content", "note")}
    else:
        summary = fetch_summary(no, key)

    # 소위 정보는 위원회에 회부되고 아직 위원회 처리 전일 때만 바뀔 수 있음
    in_committee = r.get("COMMITTEE_DT") and not (r.get("CMT_PROC_DT") or r.get("PROC_DT"))
    if in_committee or not prev:
        sub = fetch_subcommittee(no, key)
    else:
        sub = {k: prev.get(k, "") for k in SUB_FIELDS} if any(prev.get(k) for k in SUB_FIELDS) else None

    rec = to_record(r, texts, f"API 호출 성공 {today()} ({mode})", summary, sub)
    same = prev and "lead_proposer" in prev and all(prev.get(k) == rec[k] for k in COLUMNS if k not in IGNORE_IN_COMPARE)
    if same:
        print(f"[{no}] 변경 없음 ({rec['status']})")
        return prev  # 날짜 칸도 그대로 두어 파일이 바뀌지 않게 함
    (OUT / f"raw_{no}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{no}] {rec['bill_name']} / {rec['status']} ({rec['status_date']}) / 원문: {rec['text_source']}")
    return rec


def main():
    bill_nos = sys.argv[1:] or read_bill_list()
    if not bill_nos:
        print("조회할 의안번호가 없습니다. 예: python fetch_bill.py 2218220  또는 bills.txt 에 번호를 적으세요.")
        return
    old_file = OUT / "bills.json"
    old_records = json.loads(old_file.read_text(encoding="utf-8")) if old_file.exists() else []
    previous = {r["bill_id"]: r for r in old_records}
    key = load_key()
    mode = "인증키 사용" if key else "샘플 모드(인증키 없음)"
    print(f"호출 방식: {mode}")
    texts_file = BASE / "data" / "bill_texts.json"
    texts = json.loads(texts_file.read_text(encoding="utf-8")) if texts_file.exists() else {}
    OUT.mkdir(exist_ok=True)

    if not sys.argv[1:]:  # 자동 업데이트(목록 실행)일 때만 새 법안 확인
        detect_new_bills(key)
        update_members(key)

    records = [rec for no in bill_nos if (rec := update_bill(no, previous.get(no), key, texts, mode))]

    if records and records != old_records:
        record_changes(old_records, records)
        save(records)
        print(f"저장 완료: {OUT}")
    else:
        print("추적 중인 법안에 변경 없음 - 파일을 고치지 않았습니다")
    print(f"이번 실행의 API 호출: {CALLS['n']}회")


if __name__ == "__main__":
    main()
