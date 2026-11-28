"""
새 법안 폴더를 만든다 (templates/bill/ 를 data/bills/<id>/ 로 복사).

    python3 scripts/new_bill.py <id>                    # 예: python3 scripts/new_bill.py rent-law
    python3 scripts/new_bill.py <id> --bill-no 2223353  # 국회 의안번호도 자동 추적 목록에 추가

id 는 영문 소문자, 숫자, 하이픈만 (폴더 이름, 영상 경로, 앱 주소에 쓰임).
만들어지는 것: bill.json(앱 카드, draft: true), shorts.json(쇼츠 문구), sources.md(조사 자료)
그리고 data/app/settings.json 의 bill_order 맨 뒤에 id 를 넣는다.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        sys.exit(1)
    bid = args[0]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", bid):
        sys.exit("id 는 영문 소문자, 숫자, 하이픈만 쓸 수 있습니다 (예: rent-law)")
    dst = ROOT / "data" / "bills" / bid
    if dst.exists():
        sys.exit(f"이미 있습니다: data/bills/{bid}")
    shutil.copytree(ROOT / "templates" / "bill", dst)
    for name in ("bill.json", "shorts.json"):
        f = dst / name
        f.write_text(f.read_text(encoding="utf-8").replace("__ID__", bid), encoding="utf-8")

    sp = ROOT / "data" / "app" / "settings.json"
    settings = json.loads(sp.read_text(encoding="utf-8"))
    settings.setdefault("bill_order", []).append(bid)
    sp.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if "--bill-no" in args:
        no = args[args.index("--bill-no") + 1]
        shorts = dst / "shorts.json"
        s = json.loads(shorts.read_text(encoding="utf-8"))
        s["bill_meta"]["bill_no"] = no
        shorts.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tp = ROOT / "data" / "assembly" / "tracked.json"
        tracked = json.loads(tp.read_text(encoding="utf-8"))
        if no not in {str(t["bill_no"]) for t in tracked}:
            tracked.append({"bill_no": no, "memo": bid})
            tp.write_text("[\n" + ",\n".join("  " + json.dumps(t, ensure_ascii=False) for t in tracked) + "\n]\n", encoding="utf-8")
            print(f"국회 자동 추적에 추가: {no}")

    print(f"""만들었습니다: data/bills/{bid}/
다음 순서 (자세한 설명은 docs/새_법안_추가하기.md):
  1. sources.md 에 기사와 의안정보 정리
  2. shorts.json 채우기 (shorts/prompt.md 를 LLM에 주면 자료로 만들어 줌) → 사람이 검수
  3. python3 shorts/render.py data/bills/{bid}/shorts.json --preview   (미리보기)
     python3 shorts/render.py data/bills/{bid}/shorts.json             (shorts.mp4, poster.jpg)
  4. bill.json 채우기 (templates/prompt_bill_card.md) → "draft": false
  5. python3 scripts/build_site.py --serve 로 확인 후 커밋""")


if __name__ == "__main__":
    main()
