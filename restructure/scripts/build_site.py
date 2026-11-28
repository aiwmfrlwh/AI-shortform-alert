"""
웹앱 배포 폴더(_site/)를 만든다. GitHub Pages 배포와 내 컴퓨터 미리보기가 똑같이 이 스크립트를 쓴다.

    python3 scripts/build_site.py           # 검사 + _site/ 만들기
    python3 scripts/build_site.py --check   # 검사만 (파일을 만들지 않음)
    python3 scripts/build_site.py --serve   # 만들고 http://localhost:8000 에서 보기

하는 일
1. data/ 의 데이터를 검사한다 (필수 항목, 폴더 이름과 id, settings.json 의 법안 목록, 쇼츠 문구의 중간점 규칙).
2. web/ 코드를 _site/ 로 복사한다.
3. data/bills/<id>/bill.json 을 모두 모아 ("draft": true 인 것은 빼고) _site/data/bills/index.json 한 파일로 만든다
   (쇼츠 영상과 썸네일이 있으면 경로를 함께 넣는다). 영상과 썸네일도 같은 경로로 복사한다.
4. data/app/*.json, data/assembly/bills.json, new_bills.json 을 같은 경로로 복사한다.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "_site"

BILL_REQUIRED = ["id", "short", "title", "cat", "cats", "cur", "status", "when", "summary", "pro", "con", "sources"]
ASSEMBLY_FILES = ["bills.json", "new_bills.json", "members.json"]
SCREEN_KEYS = ("category", "hook", "what", "pro", "con", "status", "next")  # shorts/render.py 의 screen_texts 와 같은 범위
MIDDLE_DOTS = "·ㆍ•‧･"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_notes(obj):
    """'_설명' 처럼 밑줄로 시작하는 키는 사람용 메모라서 앱에 싣지 않는다."""
    if isinstance(obj, dict):
        return {k: strip_notes(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_notes(v) for v in obj]
    return obj


def walk_strings(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if not k.startswith("_"):
                yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_strings(v, f"{path}[{i}]")


def check():
    errors = []
    settings = load(DATA / "app" / "settings.json")
    cats = {c["name"] for c in load(DATA / "app" / "categories.json")}
    bills = {}
    for d in sorted((DATA / "bills").iterdir()):
        if not d.is_dir():
            continue
        where = f"data/bills/{d.name}"
        bj = d / "bill.json"
        if not bj.exists():
            errors.append(f"{where}: bill.json 이 없습니다")
            continue
        b = strip_notes(load(bj))
        for k in BILL_REQUIRED:
            if k not in b:
                errors.append(f"{where}/bill.json: '{k}' 항목이 없습니다")
        if b.get("id") != d.name:
            errors.append(f"{where}/bill.json: id('{b.get('id')}')가 폴더 이름과 같아야 합니다")
        if not isinstance(b.get("cur"), int) or not 0 <= b.get("cur", -1) <= 5:
            errors.append(f"{where}/bill.json: cur 는 0~5 숫자여야 합니다")
        if len(b.get("subs", [""] * 6)) != 6:
            errors.append(f"{where}/bill.json: subs 는 6칸이어야 합니다 (단계마다 한 칸)")
        for c in b.get("cats", []):
            if c not in cats:
                errors.append(f"{where}/bill.json: cats 의 '{c}' 가 data/app/categories.json 에 없습니다")
        for s in b.get("sources", []):
            if not (isinstance(s, dict) and s.get("outlet") and s.get("url")):
                errors.append(f"{where}/bill.json: sources 는 {{\"outlet\": 매체, \"url\": 주소}} 형식이어야 합니다")
                break
        sj = d / "shorts.json"
        if sj.exists():
            s = load(sj)
            if s.get("id") != d.name:
                errors.append(f"{where}/shorts.json: id('{s.get('id')}')가 폴더 이름과 같아야 합니다")
            if not s.get("allow_middle_dot"):  # 화면에 나오는 칸만 (출처 제목, URL, bill_meta 는 화면에 안 나옴)
                shown = {k: s[k] for k in SCREEN_KEYS if k in s}
                shown["sources"] = [{"outlet": x.get("outlet", "")} for x in s.get("sources", []) if isinstance(x, dict)]
                for p, text in walk_strings(shown):
                    if any(ch in text for ch in MIDDLE_DOTS):
                        errors.append(f"{where}/shorts.json: [{p}] 쇼츠 화면 문구에 중간점(·)이 있습니다: {text}")
            if not (d / "shorts.mp4").exists():
                print(f"  알림: {where} 에 shorts.json 은 있는데 shorts.mp4 가 없습니다 (python3 shorts/render.py {where}/shorts.json)")
        bills[d.name] = b
    for bid in settings.get("bill_order", []):
        if bid not in bills:
            errors.append(f"data/app/settings.json: bill_order 의 '{bid}' 폴더가 data/bills/ 에 없습니다")
    for k in ("welcome_bill",):
        if settings.get(k) and settings[k] not in bills:
            errors.append(f"data/app/settings.json: {k} '{settings[k]}' 폴더가 data/bills/ 에 없습니다")
    return errors, bills, settings


def build(bills, settings):
    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(ROOT / "web", SITE)
    order = settings.get("bill_order", [])
    ready = {i: b for i, b in bills.items() if not b.get("draft")}  # draft: true 인 법안은 아직 앱에 싣지 않는다
    for i in sorted(set(bills) - set(ready)):
        print(f"  작성 중(draft)이라 앱에서 뺌: data/bills/{i}")
    bills = ready
    ids = [i for i in order if i in bills] + sorted(i for i in bills if i not in order)
    index = []
    for bid in ids:
        b = dict(bills[bid])
        src, dst = DATA / "bills" / bid, SITE / "data" / "bills" / bid
        dst.mkdir(parents=True, exist_ok=True)
        for name, key in (("shorts.mp4", "video"), ("poster.jpg", "poster")):
            if (src / name).exists():
                shutil.copy2(src / name, dst / name)
                b[key] = f"data/bills/{bid}/{name}"
            else:
                b[key] = None
        index.append(b)
    (SITE / "data" / "bills" / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    (SITE / "data" / "app").mkdir(parents=True, exist_ok=True)
    for f in (DATA / "app").glob("*.json"):
        (SITE / "data" / "app" / f.name).write_text(
            json.dumps(strip_notes(load(f)), ensure_ascii=False), encoding="utf-8")
    (SITE / "data" / "assembly").mkdir(parents=True, exist_ok=True)
    for name in ASSEMBLY_FILES:
        f = DATA / "assembly" / name
        if f.exists():
            shutil.copy2(f, SITE / "data" / "assembly" / name)
    print(f"완성: {SITE.relative_to(ROOT)}/ (법안 {len(index)}개, 쇼츠 {sum(1 for b in index if b['video'])}개)")


def main():
    errors, bills, settings = check()
    if errors:
        print("데이터를 고쳐야 합니다:")
        for e in errors:
            print("  - " + e)
        sys.exit(1)
    print(f"데이터 검사 통과: 법안 {len(bills)}개")
    if "--check" in sys.argv:
        return
    build(bills, settings)
    if "--serve" in sys.argv:
        import functools
        import http.server
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
        print("http://localhost:8000 에서 보세요 (끝내려면 Ctrl+C)")
        http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    main()
