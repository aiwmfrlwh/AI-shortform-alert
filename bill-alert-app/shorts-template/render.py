#!/usr/bin/env python3
"""법안톡 60초 법안 쇼츠 템플릿 렌더러.

사용법:
    python3 render.py data/<bill>.json [--preview] [--out OUT_DIR]

- 모든 문구는 JSON(schema.json)에서 읽는다. 디자인(색·폰트·배치·애니메이션·장면 길이)은
  bill-alert-app/shorts/make_shorts.py(승인된 건보 특사경법 쇼츠)와 동일하다.
- 글자 규칙: 화면에 나오는 문구에 단어 사이 중간점(· ㆍ • ‧ ･)을 쓰지 않는다.
  들어 있으면 검증 단계에서 오류로 멈춘다. 렌더러가 자동으로 붙이는 구분자도 중간점 대신
  쉼표와 콜론을 쓴다. 규칙 이전에 만든 영상을 그대로 재현할 때만 JSON에 "allow_middle_dot": true.
- --preview : 장면별로 요소가 모두 등장한 시점의 1080x1920 PNG + 컨택트시트만 저장
- 전체 렌더 : 장면별 mp4 → concat(-c copy) → 합성 패드 음악 추가 → OUT_DIR/<id>_쇼츠.mp4
"""
import argparse, json, math, os, re, subprocess, sys, wave
from datetime import date

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))

W, H, FPS = 1080, 1920, 30
FD = '/usr/share/fonts/opentype/noto/'
_FONT_CACHE = {}


def F(w, s):
    key = (w, s)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(
            FD + {'bk': 'NotoSansCJK-Black.ttc', 'b': 'NotoSansCJK-Bold.ttc',
                  'm': 'NotoSansCJK-Medium.ttc', 'r': 'NotoSansCJK-Regular.ttc'}[w], s, index=1)
    return _FONT_CACHE[key]


BG = (14, 15, 18)
INK = (255, 255, 255)
MUTED = (176, 180, 189)
BLUE = (110, 140, 255)
BLUE_D = (35, 70, 216)
ORANGE = (249, 115, 22)
CARD = (30, 32, 38)
LINE = (58, 61, 70)
GREEN = (52, 199, 120)
TODO = (120, 124, 133)
SRC = (130, 134, 143)

L = 80                    # 왼쪽 여백
CONTENT_W = W - 2 * L     # 920: 본문 최대 폭
CARD_W = 920
CARD_PAD = 44
CARD_TEXT_W = CARD_W - 2 * CARD_PAD   # 832
SAFE_BOTTOM = 1640        # (+90 오프셋 전 기준) 이 아래는 쇼츠 UI(자막·버튼)에 가려질 수 있음
MIN_GAP = 24              # 흐름 배치 시 요소 사이 최소 간격

SCENE_DUR = {'hook': 4.6, 'what': 7.2, 'pro': 8.0, 'con': 7.6, 'status': 10.0, 'next': 6.4}
SCENE_ORDER = ['hook', 'what', 'pro', 'con', 'status', 'next']
DEFAULT_STAGE_LABELS = ['발의', '소관위 회부', '소관위 심사', '법사위 심사', '본회의', '정부 이송과 공포']
LEGACY_STAGE_LABELS = ['발의', '소관위 회부', '소관위 심사', '법사위 체계·자구', '본회의', '정부 이송·공포']
MIDDLE_DOTS = '·ㆍ•‧･'   # 화면 문구에 쓰면 안 되는 중간점 종류


def legacy(data):
    """중간점 규칙 이전에 만든 영상(원본 재현용)인지."""
    return data.get('allow_middle_dot') is True


def seps(data):
    """렌더러가 자동으로 붙이는 구분자. 기본은 중간점 없이, 예전 영상 재현 때만 원래 모양."""
    if legacy(data):
        return {'date': ' · ', 'side': ' · ', 'src': '·', 'labels': LEGACY_STAGE_LABELS}
    return {'date': ', ', 'side': ': ', 'src': ', ', 'labels': DEFAULT_STAGE_LABELS}


def screen_texts(data):
    """(필드 경로, 화면에 나오는 문구) 목록. bill_meta와 출처 제목·URL은 화면에 안 나와서 제외."""
    out = []

    def add(path, v):
        if isinstance(v, str) and v.strip():
            out.append((path, v))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                add(f'{path}[{i}]', x)
        elif isinstance(v, dict):
            for k, x in v.items():
                add(f'{path}.{k}', x)

    for key in ('category', 'hook', 'what', 'pro', 'con', 'status', 'next'):
        if key in data:
            add(key, data[key])
    for i, src in enumerate(data.get('sources') or []):
        if isinstance(src, dict):
            add(f'sources[{i}].outlet', src.get('outlet'))
    return out


class FitError(ValueError):
    pass


# ---------- 텍스트 맞춤(fitting) ----------
def parse_marked(s, hi):
    """'**강조**' 표기를 (텍스트, 색) 세그먼트로."""
    segs = []
    for i, part in enumerate(re.split(r'\*\*', s)):
        if part:
            segs.append((part, hi if i % 2 else INK))
    return segs


def seg_width(font, segs):
    return sum(font.getlength(t) for t, _ in segs)


def fit_size(field, lines, size, floor, weight, max_w):
    """lines: [[(text,color),...], ...]. max_w 안에 들어가는 가장 큰 크기(size→floor, 2px 단위)."""
    s = size
    while True:
        font = F(weight, s)
        worst = max(((seg_width(font, l), i) for i, l in enumerate(lines)), default=(0, 0))
        if worst[0] <= max_w:
            return s
        if s <= floor:
            txt = ''.join(t for t, _ in lines[worst[1]])
            raise FitError(f'[{field}] 줄 {worst[1] + 1} "{txt}" 이(가) 너무 깁니다 '
                           f'(최소 글자크기 {floor}px에서도 {int(worst[0])}px > 허용 {max_w}px). 문구를 줄이세요.')
        s = max(floor, s - 2)


# ---------- 요소 빌더 (RGBA 사전 렌더) ----------
def text_el(lines, size, w='b', color=INK, gap=1.28):
    """lines: list of str or list of (str,color) segments"""
    font = F(w, size)
    lh = int(size * gap)
    segs_lines = [[(l, color)] if isinstance(l, str) else l for l in lines]
    widths = [sum(font.getlength(t) for t, _ in sl) for sl in segs_lines]
    im = Image.new('RGBA', (int(max(widths)) + 8, lh * len(lines) + int(size * 0.35)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, sl in enumerate(segs_lines):
        x = 0
        for t, c in sl:
            d.text((x, i * lh), t, font=font, fill=c)
            x += font.getlength(t)
    return im


def fit_text_el(field, lines, size, floor, w='b', color=INK, gap=1.28, max_w=CONTENT_W, hi=None):
    segs = [parse_marked(l, hi) if hi else [(l, color)] for l in lines]
    s = fit_size(field, segs, size, floor, w, max_w)
    return text_el(segs, s, w, color, gap)


def chip_el(text, size=34, fg=INK, bg=(255, 255, 255, 38), padx=24, pady=12, w='b'):
    font = F(w, size)
    tw = font.getlength(text)
    hh = int(size * 1.45) + pady
    im = Image.new('RGBA', (int(tw) + padx * 2, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, hh - 1), radius=hh // 2 if size < 40 else 18, fill=bg)
    d.text((padx, (hh - size * 1.42) / 2), text, font=font, fill=fg)
    return im


def fit_chip_el(field, text, size, floor, padx, max_w=CONTENT_W, w='b', **kw):
    s = fit_size(field, [[(text, INK)]], size, floor, w, max_w - 2 * padx)
    return chip_el(text, s, padx=padx, w=w, **kw)


def card_el(w_, rows, bg=CARD, pad=CARD_PAD, radius=36, accent=None):
    """rows: list of (text, size, weight, color) or ('gap', px)"""
    hs = []
    for r in rows:
        hs.append(r[1] if r[0] == 'gap' else int(r[1] * 1.42))
    h_ = sum(hs) + pad * 2
    im = Image.new('RGBA', (w_, h_), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w_ - 1, h_ - 1), radius=radius, fill=bg)
    if accent:
        d.rounded_rectangle((0, 0, w_ - 1, h_ - 1), radius=radius, outline=accent, width=4)
    y = pad
    for r, hh in zip(rows, hs):
        if r[0] != 'gap':
            d.text((pad, y), r[0], font=F(r[2], r[1]), fill=r[3])
        y += hh
    return im


def fit_card_el(field, groups):
    """groups: [(subfield, [texts], size, floor, weight, color)] — 그룹별로 같은 크기로 맞춤."""
    rows = []
    for sub, texts, size, floor, wt, col in groups:
        texts = [t for t in texts if t]
        if not texts:
            continue
        s = fit_size(f'{field}.{sub}', [[(t, INK)] for t in texts], size, floor, wt, CARD_TEXT_W)
        rows += [(t, s, wt, col) for t in texts]
    return card_el(CARD_W, rows)


# ---------- 애니메이션 ----------
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


class Scene:
    def __init__(self, name, dur, idx, total):
        self.name, self.dur, self.idx, self.total = name, dur, idx, total
        self.els = []     # (img, x, y, t_in, kind)
        self.custom = []  # fn(canvas, draw, t, out)
        self.last_t = 0.0

    def add(self, img, x, y, t, kind='up'):
        self.els.append((img, x, y + 90, t, kind))
        self.last_t = max(self.last_t, t)
        return img

    def busiest_t(self):
        """모든 요소가 다 들어온 직후(페이드아웃 전)."""
        return min(self.dur - 0.4, self.last_t + 0.8)

    def frame(self, t):
        c = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(c)
        draw_chrome(c, d, self.idx, t / self.dur, self.total)
        out = 1.0 if t < self.dur - 0.35 else ease((self.dur - t) / 0.35)
        for fn in self.custom:
            fn(c, d, t, out)
        for img, x, y, t0, kind in self.els:
            p = ease((t - t0) / 0.45)
            a = p * out
            if a <= 0.01:
                continue
            dy = int((1 - p) * 48) if kind == 'up' else 0
            if kind == 'pop':
                s = 0.85 + 0.15 * ease((t - t0) / 0.3)
                im = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))))
                xx, yy = x + (img.width - im.width) // 2, y + (img.height - im.height) // 2
            else:
                im, xx, yy = img, x, y + dy
            m = im.getchannel('A').point(lambda v, a=a: int(v * a))
            c.paste(im.convert('RGB'), (xx, yy), m)
        return c


def draw_chrome(c, d, idx, prog, n_scenes):
    # 스토리 진행 바
    x0, x1, y = 60, W - 60, 70
    gap = 12
    sw = (x1 - x0 - gap * (n_scenes - 1)) / n_scenes
    for i in range(n_scenes):
        sx = x0 + i * (sw + gap)
        d.rounded_rectangle((sx, y, sx + sw, y + 8), radius=4, fill=(70, 73, 82))
        fill = 1 if i < idx else (prog if i == idx else 0)
        if fill > 0:
            d.rounded_rectangle((sx, y, sx + max(8, sw * fill), y + 8), radius=4, fill=INK)
    # 브랜드
    d.rounded_rectangle((60, 112, 124, 176), radius=16, fill=BLUE_D)
    ix, iy = 72, 124
    d.line([(ix + 4, iy + 16), (ix + 20, iy + 6), (ix + 36, iy + 16)], fill=INK, width=4)
    for k in range(4):
        xx = ix + 8 + k * 8
        d.line([(xx, iy + 18), (xx, iy + 34)], fill=INK, width=3)
    d.line([(ix + 2, iy + 37), (ix + 38, iy + 37)], fill=INK, width=4)
    d.text((140, 116), '법안톡', font=F('b', 38), fill=INK)
    d.text((272, 124), '· 60초 법안 요약', font=F('m', 30), fill=MUTED)


class Flow:
    """원본 배치(anchor y)를 지키되, 앞 요소가 길어지면 그만큼 아래로 밀어내는 세로 배치기."""

    def __init__(self, field):
        self.bottom = 0
        self.field = field

    def place(self, img, anchor):
        y = max(anchor, self.bottom + MIN_GAP) if self.bottom else anchor
        self.bottom = y + img.height
        if self.bottom > SAFE_BOTTOM:
            raise FitError(f'[{self.field}] 장면 내용이 화면 아래 안전 영역을 넘습니다 '
                           f'(하단 {self.bottom}px > {SAFE_BOTTOM}px). 줄 수나 카드 줄을 줄이세요.')
        return y


# ---------- 검증 ----------
def nonempty(v):
    if v is None:
        return False
    if isinstance(v, str):
        return v.strip() != ''
    if isinstance(v, (list, tuple)):
        return any(nonempty(x) for x in v)
    if isinstance(v, dict):
        return any(nonempty(x) for x in v.values())
    return True


def clean_lines(v):
    return [x for x in (v or []) if isinstance(x, str) and x.strip()]


def side_present(side):
    """찬성/반대 장면은 '누가' + (인용 또는 카드)가 있어야 보여준다."""
    if not side:
        return False
    return nonempty(side.get('who')) and (nonempty(side.get('quote_lines')) or nonempty(side.get('cards')))


def validate(data):
    errs = []
    try:
        import jsonschema
        with open(os.path.join(HERE, 'schema.json'), encoding='utf-8') as f:
            schema = json.load(f)
        v = jsonschema.Draft202012Validator(schema)
        for e in sorted(v.iter_errors(data), key=lambda e: list(e.path)):
            path = '.'.join(str(p) for p in e.path) or '(root)'
            errs.append(f'{path}: {e.message}')
    except ImportError:
        pass

    def req(path):
        cur = data
        for k in path.split('.'):
            if not isinstance(cur, dict) or k not in cur:
                errs.append(f'{path}: 필수 필드가 없습니다')
                return None
            cur = cur[k]
        if not nonempty(cur):
            errs.append(f'{path}: 비어 있으면 안 됩니다')
        return cur

    for p in ['id', 'as_of', 'category', 'hook.title_lines', 'hook.bill_name', 'hook.status',
              'what.summary_lines', 'status.stage', 'status.chip', 'sources']:
        req(p)
    if isinstance(data.get('id'), str) and not re.fullmatch(r'[a-z0-9][a-z0-9-]*', data['id']):
        errs.append('id: 영문 소문자·숫자·하이픈만 사용하세요 (파일명에 쓰임)')
    try:
        date.fromisoformat(str(data.get('as_of')))
    except ValueError:
        errs.append('as_of: YYYY-MM-DD 형식이어야 합니다')
    st = data.get('status', {})
    stage = st.get('stage')
    if not isinstance(stage, int) or isinstance(stage, bool) or not 0 <= stage <= 5:
        errs.append('status.stage: 0~5 정수여야 합니다 (0 발의, 1 소관위 회부, 2 소관위 심사, 3 법사위 심사, 4 본회의, 5 정부 이송과 공포)')
    for key, lo, hi in [('labels', 6, 6), ('details', 6, 6)]:
        v = st.get(key)
        if v is not None and not (isinstance(v, list) and lo <= len(v) <= hi):
            errs.append(f'status.{key}: 정확히 6개 항목(단계 0~5)이어야 합니다')
    if st.get('labels') is not None and isinstance(st.get('labels'), list) and not all(nonempty(x) for x in st['labels']):
        errs.append('status.labels: 단계 이름은 비울 수 없습니다 (생략하면 기본 이름 사용)')
    for k, lo, hi in [('hook.title_lines', 1, 4), ('what.summary_lines', 1, 3), ('next.lines', 0, 3)]:
        a, b = k.split('.')
        v = (data.get(a) or {}).get(b)
        n = len(clean_lines(v)) if isinstance(v, list) else 0
        if isinstance(v, list) and not lo <= n <= hi:
            errs.append(f'{k}: {lo}~{hi}줄이어야 합니다 (현재 {n}줄)')
    cards = (data.get('what') or {}).get('cards') or []
    if len(cards) > 2:
        errs.append('what.cards: 최대 2개')
    for side in ('pro', 'con'):
        sd = data.get(side) or {}
        if nonempty(sd) and not side_present(sd):
            errs.append(f'{side}: 내용을 넣으려면 who와 quote_lines(또는 cards)가 모두 있어야 합니다. 자료가 없으면 {side} 전체를 비우세요')
        if len(clean_lines(sd.get('quote_lines'))) > 2:
            errs.append(f'{side}.quote_lines: 최대 2줄')
        if len(sd.get('cards') or []) > 2:
            errs.append(f'{side}.cards: 최대 2개')
    if side_present(data.get('pro')) != side_present(data.get('con')):
        errs.append('pro/con: 찬성과 반대는 균형을 위해 둘 다 채우거나 둘 다 비워야 합니다')
    if not legacy(data):
        for path, txt in screen_texts(data):
            if any(ch in txt for ch in MIDDLE_DOTS):
                errs.append(f'{path}: 단어 사이 중간점을 쓰지 마세요 → "{txt}" '
                            f'(쉼표, "와/과", 띄어쓰기로 바꾸기. 예: "교통·안전" → "교통 안전")')
    srcs = data.get('sources') or []
    for i, s in enumerate(srcs):
        if not isinstance(s, dict) or not nonempty(s.get('outlet')):
            errs.append(f'sources[{i}]: outlet은 필수입니다')
    if errs:
        raise ValueError('JSON 검증 실패:\n  - ' + '\n  - '.join(dict.fromkeys(errs)))


# ---------- 장면 구성 ----------
def fmt_date(iso):
    d = date.fromisoformat(iso)
    return f'{d.year}.{d.month:02d}.{d.day:02d}'


def balanced_wrap(prefix, items, suffix, font, max_w, sep=', '):
    """출처 문구: 한 줄에 들어가면 한 줄, 아니면 두 줄의 최대폭이 최소가 되게 구분자에서 나눔."""
    full = prefix + sep.join(items) + suffix
    if font.getlength(full) <= max_w:
        return [full]
    best = None
    for k in range(1, len(items)):
        a = prefix + sep.join(items[:k]) + sep
        a = a.rstrip() if sep.strip() else a
        b = sep.join(items[k:]) + suffix
        m = max(font.getlength(a), font.getlength(b))
        if best is None or m < best[0]:
            best = (m, [a, b])
    if best is None or best[0] > max_w:
        return None
    return best[1]


def build_scenes(data):
    present = ['hook', 'what']
    if side_present(data.get('pro')) and side_present(data.get('con')):
        present += ['pro', 'con']
    present += ['status', 'next']
    total = len(present)
    scenes = []
    sp = seps(data)

    def new(name):
        s = Scene(name, SCENE_DUR[name], len(scenes), total)
        scenes.append(s)
        return s

    # S1 hook
    hk = data['hook']
    s = new('hook')
    s.add(fit_chip_el('category', data['category'], 34, 28, 24, fg=INK, bg=(110, 140, 255, 70)), L, 300, 0.1)
    fl = Flow('hook')
    fl.bottom = 300 + s.els[-1][0].height
    title = fit_text_el('hook.title_lines', clean_lines(hk['title_lines']), 96, 80, 'bk', gap=1.24, hi=BLUE)
    ty = fl.place(title, 400)
    s.add(title, L, ty, 0.35)
    # 제목이 4줄보다 짧으면 법안명·상태 칩을 위로 당겨 빈 공간을 줄임 (4줄일 때 원본과 동일: 1000, 1100)
    sub = fit_text_el('hook.bill_name', [f"{hk['bill_name']}{sp['date']}{fmt_date(data['as_of'])} 기준"], 34, 28, 'm', MUTED)
    sy = ty + title.height + 91
    s.add(sub, L, fl.place(sub, sy), 1.0)
    chip = fit_chip_el('hook.status', f"현재: {hk['status']}", 38, 32, 30, fg=(20, 12, 4), bg=ORANGE + (255,), pady=16)
    s.add(chip, L, fl.place(chip, sy + sub.height + 46), 1.6, 'pop')

    # S2 what
    wt = data['what']
    s = new('what')
    s.add(text_el(['무슨 법안이야?'], 44, 'b', BLUE), L, 300, 0.1)
    fl = Flow('what')
    fl.bottom = 300
    summ = fit_text_el('what.summary_lines', clean_lines(wt['summary_lines']), 76, 64, 'bk', gap=1.3, hi=ORANGE)
    s.add(summ, L, fl.place(summ, 380), 0.4)
    anchors, times = [760, 1080], [1.4, 2.4]
    cards = [c for c in (wt.get('cards') or []) if nonempty(c)]
    if not cards:
        cards = meta_cards(data.get('bill_meta') or {})
    for i, cd in enumerate(cards):
        el = fit_card_el(f'what.cards[{i}]', [('label', [cd.get('label', '')], 32, 28, 'm', MUTED),
                                               ('lines', clean_lines(cd.get('lines'))[:2], 46, 38, 'b', INK)])
        s.add(el, L, fl.place(el, anchors[i]), times[i])

    # S3/S4 pro, con
    if 'pro' in present:
        for side in ('pro', 'con'):
            sd = data[side]
            s = new(side)
            if side == 'pro':
                chip = fit_chip_el('pro.who', f"찬성{sp['side']}{sd['who']}", 36, 30, 28, fg=(8, 30, 18), bg=GREEN + (255,), pady=14)
            else:
                chip = fit_chip_el('con.who', f"반대{sp['side']}{sd['who']}", 36, 30, 28, fg=(30, 8, 8), bg=(255, 120, 120, 255), pady=14)
            s.add(chip, L, 300, 0.1)
            fl = Flow(side)
            fl.bottom = 300 + chip.height
            q = clean_lines(sd.get('quote_lines'))
            if q:
                q = q[:]
                q[0] = '“' + q[0]
                q[-1] = q[-1] + '”'
                qe = fit_text_el(f'{side}.quote_lines', q, 72, 60, 'bk', gap=1.3)
                s.add(qe, L, fl.place(qe, 400), 0.4)
            cards = [c for c in (sd.get('cards') or []) if nonempty(c)]
            if side == 'pro':
                anchors, times = [660, 1060], [1.3, 2.6]
                for i, cd in enumerate(cards):
                    el = fit_card_el(f'pro.cards[{i}]', [('label', [cd.get('label', '')], 32, 28, 'm', MUTED),
                                                          ('value', [cd.get('value', '')], 84 if i == 0 else 64, 48, 'bk', INK),
                                                          ('note', [cd.get('note', '')], 38, 32, 'b', INK)])
                    s.add(el, L, fl.place(el, anchors[i]), times[i])
                if nonempty(sd.get('note')):
                    ne = fit_text_el('pro.note', [sd['note']], 28, 24, 'r', MUTED)
                    s.add(ne, L, fl.place(ne, 1420), 3.2)
            else:
                anchors, times = [660, 1000], [1.3, 2.4]
                for i, cd in enumerate(cards):
                    el = fit_card_el(f'con.cards[{i}]', [('title', [cd.get('title', '')], 48, 40, 'b', INK),
                                                          ('lines', clean_lines(cd.get('lines'))[:2], 38, 32, 'm', MUTED)])
                    s.add(el, L, fl.place(el, anchors[i]), times[i])
                if nonempty(sd.get('note')):
                    ne = fit_text_el('con.note', [sd['note']], 32, 26, 'm', BLUE)
                    s.add(ne, L, fl.place(ne, 1290), 3.4)

    # S5 status timeline
    st = data['status']
    s = new('status')
    s.add(text_el(['지금 어디까지 왔나?'], 64, 'bk'), L, 290, 0.1)
    labels = st.get('labels') or sp['labels']
    details = st.get('details') or [''] * 6
    stage = st['stage']
    steps = [(labels[i], details[i] or '', 'done' if i < stage else ('now' if i == stage else 'todo')) for i in range(6)]
    TY0, TSTEP = 450, 170
    TY0E = TY0 + 90
    for i, (lab, sub, stt) in enumerate(steps):
        col = INK if stt != 'todo' else TODO
        if stt == 'now':
            chip_txt = st['chip']
            chip_tmp = chip_el(chip_txt, 34, padx=22, pady=10)
            lab_size = fit_size(f'status.labels[{i}]', [[(lab, INK)]], 50, 40, 'bk', 1000 - 190 - 20 - chip_tmp.width)
            lab_el = text_el([lab], lab_size, 'bk', ORANGE)
        else:
            lab_el = fit_text_el(f'status.labels[{i}]', [lab], 46, 38, 'b', col, max_w=1000 - 190)
        s.add(lab_el, 190, TY0 + i * TSTEP - 8, 0.6 + i * 0.55)
        if sub:
            s.add(fit_text_el(f'status.details[{i}]', [sub], 32, 26, 'm', MUTED if stt != 'now' else (255, 200, 160), max_w=1000 - 190),
                  190, TY0 + i * TSTEP + 62, 0.75 + i * 0.55)
        if stt == 'now':
            s.add(fit_chip_el('status.chip', st['chip'], 34, 34, 22, fg=(20, 12, 4), bg=ORANGE + (255,), pady=10, max_w=300),
                  190 + lab_el.width + 20, TY0 + i * TSTEP - 2, 0.9 + i * 0.55, 'pop')

    def timeline(c, d, t, out):
        def mix(col, a):
            return tuple(int(BG[k] + (col[k] - BG[k]) * a) for k in range(3))
        cx = 120
        for i, (lab, sub, stt) in enumerate(steps):
            a = ease((t - (0.6 + i * 0.55)) / 0.4) * out
            if a <= 0:
                continue
            y = TY0E + i * TSTEP + 26
            if i < len(steps) - 1:
                nxt = ease((t - (0.9 + i * 0.55)) / 0.5)
                y2 = y + TSTEP * nxt
                lc = BLUE if stt == 'done' else LINE
                d.line([(cx, y + 26), (cx, max(y + 26, y2 - 26))], fill=mix(lc, out), width=6)
            if stt == 'done':
                d.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=mix(BLUE_D, a))
                d.line([(cx - 11, y), (cx - 3, y + 9), (cx + 12, y - 9)], fill=mix(INK, a), width=6)
            elif stt == 'now':
                pulse = 0.5 + 0.5 * math.sin(t * 5)
                r = 24 + 14 * pulse
                d.ellipse((cx - r, y - r, cx + r, y + r), fill=mix((90, 45, 15), a))
                d.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=mix(ORANGE, a))
                d.rectangle((cx - 9, y - 11, cx - 3, y + 11), fill=mix(BG, a))
                d.rectangle((cx + 3, y - 11, cx + 9, y + 11), fill=mix(BG, a))
            else:
                d.ellipse((cx - 22, y - 22, cx + 22, y + 22), outline=mix(TODO, a), width=5)
    s.custom.append(timeline)
    s.last_t = max(s.last_t, 0.9 + 5 * 0.55 + 0.5)

    # S6 next + CTA
    nx = data.get('next') or {}
    s = new('next')
    nlines = clean_lines(nx.get('lines'))
    fl = Flow('next')
    if nlines:
        s.add(text_el(['다음은?'], 44, 'b', BLUE), L, 300, 0.1)
        fl.bottom = 300
        ne = fit_text_el('next.lines', nlines, 72, 60, 'bk', gap=1.3, hi=ORANGE)
        s.add(ne, L, fl.place(ne, 380), 0.4)
        if nonempty(nx.get('note')):
            nn = fit_text_el('next.note', [nx['note']], 40, 34, 'm', MUTED)
            s.add(nn, L, fl.place(nn, 720), 1.2)
        btn_anchor, btn_t = 880, 1.9
    else:
        # '다음은?' 정보가 없으면 제목 없이 알림 버튼을 위로 올려 빈 화면을 피함
        s.add(text_el(['진행 상황이 바뀌면'], 44, 'b', BLUE), L, 300, 0.1)
        ne = text_el(['국회 단계가', '바뀔 때마다', [('바로 알려드려요', ORANGE)]], 72, 'bk', gap=1.3)
        s.add(ne, L, 380, 0.4)
        fl.bottom = 380 + ne.height
        if nonempty(nx.get('note')):
            nn = fit_text_el('next.note', [nx['note']], 40, 34, 'm', MUTED)
            s.add(nn, L, fl.place(nn, 720), 1.2)
        btn_anchor, btn_t = 760, 1.4
    btn = bell_btn()
    s.add(btn, L, fl.place(btn, btn_anchor), btn_t, 'pop')
    if nonempty(nx.get('cta_note')):
        cn = fit_text_el('next.cta_note', [nx['cta_note']], 34, 28, 'm', MUTED)
        s.add(cn, L, fl.place(cn, 1060), btn_t + 0.5)
    outlets = list(dict.fromkeys(src['outlet'].strip() for src in data['sources']))
    suffix = f' ({source_period(data)} 보도 종합)'
    src_lines, size = None, 28
    while size >= 22:
        src_lines = balanced_wrap('출처: ', outlets, suffix, F('r', size), CONTENT_W, sp['src'])
        if src_lines:
            break
        size -= 2
    if not src_lines:
        raise FitError('[sources] 출처 매체가 너무 많아 두 줄에 들어가지 않습니다. 대표 매체만 남기세요.')
    se = text_el(src_lines, size, 'r', SRC, gap=1.45)
    s.add(se, L, fl.place(se, 1300), btn_t + 0.9)
    return scenes


def meta_cards(meta):
    """what.cards가 비었을 때 bill_meta(발의자, 발의일, 소관위)로 대체 카드를 만들어 빈 화면을 피함."""
    out = []
    lines = [x for x in [meta.get('proposer', ''), meta.get('proposed_date', '')] if nonempty(x)]
    if lines:
        if len(lines) == 2:
            try:
                lines[1] = fmt_date(lines[1]) + ' 발의'
            except ValueError:
                pass
        out.append({'label': '누가 냈나?', 'lines': lines})
    if nonempty(meta.get('committee')):
        out.append({'label': '소관 상임위원회', 'lines': [meta['committee']]})
    return out


def source_period(data):
    """출처 기간: sources[].date(YYYY-MM-DD)가 있으면 최소~최대 월, 없으면 as_of의 월."""
    months = sorted({m.group(1) + '.' + m.group(2) for s in data['sources']
                     for m in [re.match(r'(\d{4})-(\d{2})', str(s.get('date', '')))] if m})
    if not months:
        d_ = date.fromisoformat(data['as_of'])
        return f'{d_.year}.{d_.month:02d}'
    return months[0] if len(months) == 1 else f'{months[0]}~{months[-1]}'


def bell_btn():
    w_, h_ = 920, 150
    im = Image.new('RGBA', (w_, h_), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w_ - 1, h_ - 1), radius=36, fill=BLUE_D)
    bx, by = 250, 42
    d.arc((bx, by, bx + 56, by + 60), 180, 360, fill=INK, width=7)
    d.line([(bx, by + 30), (bx, by + 56)], fill=INK, width=7)
    d.line([(bx + 56, by + 30), (bx + 56, by + 56)], fill=INK, width=7)
    d.line([(bx - 8, by + 58), (bx + 64, by + 58)], fill=INK, width=7)
    d.ellipse((bx + 20, by + 62, bx + 36, by + 76), fill=INK)
    d.text((bx + 90, 40), '이 법안 알림 받기', font=F('bk', 54), fill=INK)
    return im


# ---------- 오디오 (합성 패드) ----------
def synth_pad(path, dur, sr=44100):
    """A - G - F - G(6) 코드 진행(코드당 5.5초)의 부드러운 패드 + A1 베이스. 원본 쇼츠의 배경음과 같은 구성."""
    n = int(round(dur * sr))
    t = np.arange(n) / sr
    chords = [(220.0, 277.18, 329.63), (196.0, 246.94, 293.66), (174.61, 220.0, 261.63), (196.0, 246.94, 329.63)]
    seg = 5.5
    x = np.zeros(n)
    xf = 0.6  # 코드 전환 크로스페이드(초)
    for k in range(int(math.ceil(dur / seg)) + 1):
        t0 = k * seg
        env = np.clip((t - t0 + xf / 2) / xf, 0, 1) * np.clip((t0 + seg + xf / 2 - t) / xf, 0, 1)
        if not env.any():
            continue
        for f in chords[k % len(chords)]:
            for mult, amp in ((1, 0.11), (2, 0.045)):
                for det in (-0.6, 0.6):
                    x += env * amp * 0.5 * np.sin(2 * np.pi * (f * mult + det) * t)
    x += 0.09 * (0.8 + 0.2 * np.sin(2 * np.pi * 3.5 * t)) * np.sin(2 * np.pi * 55.0 * t)
    x *= 0.85 + 0.15 * np.sin(2 * np.pi * 0.12 * t)
    fade = np.clip(t / 1.6, 0, 1) * np.clip((dur - t) / 0.9, 0, 1)
    x *= fade
    x = x / (np.abs(x).max() + 1e-9) * 0.185
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


# ---------- 렌더 ----------
def render_scene(sc, path):
    tmp = path + '.tmp.mp4'
    n = int(round(sc.dur * FPS))
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
                          '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(sc.frame(i / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError(f'ffmpeg 장면 인코딩 실패: {sc.name}')
    os.replace(tmp, path)


def contact_sheet(pngs, path, cols=3, tw=360):
    ims = [Image.open(p) for p in pngs]
    th = int(tw * H / W)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw + (cols + 1) * 16, rows * th + (rows + 1) * 16), (40, 42, 48))
    for i, im in enumerate(ims):
        r, c = divmod(i, cols)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (16 + c * (tw + 16), 16 + r * (th + 16)))
    sheet.save(path)


def main():
    ap = argparse.ArgumentParser(description='법안톡 60초 법안 쇼츠 렌더러')
    ap.add_argument('json')
    ap.add_argument('--preview', action='store_true', help='장면별 PNG와 컨택트시트만 저장')
    ap.add_argument('--out', default=os.path.join(HERE, 'outputs'), help='최종 mp4 저장 폴더 (기본: outputs/)')
    ap.add_argument('--build', default=None, help='임시 파일 폴더 (기본: build/<id>/)')
    a = ap.parse_args()
    with open(a.json, encoding='utf-8') as f:
        data = json.load(f)
    try:
        validate(data)
        scenes = build_scenes(data)
    except (ValueError, FitError) as e:
        print(e, file=sys.stderr)
        sys.exit(2)
    bid = data['id']
    build = a.build or os.path.join(HERE, 'build', bid)
    os.makedirs(build, exist_ok=True)
    total = sum(s.dur for s in scenes)
    print(f'[{bid}] 장면 {len(scenes)}개 ({", ".join(s.name for s in scenes)}) · 총 {total:.1f}초')
    if a.preview:
        pdir = os.path.join(build, 'preview')
        os.makedirs(pdir, exist_ok=True)
        pngs = []
        for i, sc in enumerate(scenes):
            p = os.path.join(pdir, f'{i + 1}_{sc.name}.png')
            sc.frame(sc.busiest_t()).save(p)
            pngs.append(p)
        contact_sheet(pngs, os.path.join(pdir, 'contact.png'))
        print('미리보기:', pdir)
        return
    os.makedirs(a.out, exist_ok=True)
    parts = []
    for i, sc in enumerate(scenes):
        p = os.path.join(build, f's{i + 1}_{sc.name}.mp4')
        print(f'  장면 렌더: {sc.name} ({sc.dur}s)')
        render_scene(sc, p)
        parts.append(p)
    lst = os.path.join(build, 'list.txt')
    with open(lst, 'w') as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    video = os.path.join(build, 'video.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', video], check=True)
    pad = os.path.join(build, 'pad.wav')
    synth_pad(pad, total + 0.034)
    final = os.path.join(a.out, f'{bid}_쇼츠.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', video, '-i', pad, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k',
                    '-movflags', '+faststart', final], check=True)
    print('완료:', final)


if __name__ == '__main__':
    main()
