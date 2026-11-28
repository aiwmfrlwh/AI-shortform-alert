# 보관용: 템플릿(shorts/render.py) 이전에 첫 쇼츠(건보 특사경법)를 만든 원래 스크립트.
# 지금은 shorts/render.py + data/bills/gb-tsg/shorts.json 이 같은 영상을 만든다. 경로(OUT)는 당시 작업 환경 기준.
import os, sys, subprocess, math
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
OUT = '/home/claude/shorts/out'
os.makedirs(OUT, exist_ok=True)
FD = '/usr/share/fonts/opentype/noto/'
def F(w, s):
    return ImageFont.truetype(FD + {'bk': 'NotoSansCJK-Black.ttc', 'b': 'NotoSansCJK-Bold.ttc', 'm': 'NotoSansCJK-Medium.ttc', 'r': 'NotoSansCJK-Regular.ttc'}[w], s, index=1)

BG = (14, 15, 18)
INK = (255, 255, 255)
MUTED = (176, 180, 189)
BLUE = (110, 140, 255)
BLUE_D = (35, 70, 216)
ORANGE = (249, 115, 22)
CARD = (30, 32, 38)
LINE = (58, 61, 70)
GREEN = (52, 199, 120)

# ---------- element builders (pre-rendered RGBA) ----------
def text_el(lines, size, w='b', color=INK, gap=1.28, spans=None):
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

def chip_el(text, size=34, fg=INK, bg=(255, 255, 255, 38), padx=24, pady=12, w='b'):
    font = F(w, size)
    tw = font.getlength(text)
    hh = int(size * 1.45) + pady
    im = Image.new('RGBA', (int(tw) + padx * 2, hh), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, hh - 1), radius=hh // 2 if size < 40 else 18, fill=bg)
    d.text((padx, (hh - size * 1.42) / 2), text, font=font, fill=fg)
    return im

def card_el(w_, rows, bg=CARD, pad=44, radius=36, accent=None):
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

# ---------- animation ----------
def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3

class Scene:
    def __init__(self, name, dur, idx):
        self.name, self.dur, self.idx = name, dur, idx
        self.els = []   # (img, x, y, t_in, kind)
        self.custom = []  # fn(canvas, draw, t)
    def add(self, img, x, y, t, kind='up'):
        self.els.append((img, x, y + 90, t, kind)); return img
    def frame(self, t):
        c = Image.new('RGB', (W, H), BG)
        d = ImageDraw.Draw(c)
        draw_chrome(c, d, self.idx, t / self.dur)
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

N_SCENES = 6
def draw_chrome(c, d, idx, prog):
    # story progress bars
    x0, x1, y = 60, W - 60, 70
    gap = 12
    sw = (x1 - x0 - gap * (N_SCENES - 1)) / N_SCENES
    for i in range(N_SCENES):
        sx = x0 + i * (sw + gap)
        d.rounded_rectangle((sx, y, sx + sw, y + 8), radius=4, fill=(70, 73, 82))
        fill = 1 if i < idx else (prog if i == idx else 0)
        if fill > 0:
            d.rounded_rectangle((sx, y, sx + max(8, sw * fill), y + 8), radius=4, fill=INK)
    # brand
    d.rounded_rectangle((60, 112, 124, 176), radius=16, fill=BLUE_D)
    # building icon
    ix, iy = 72, 124
    d.line([(ix + 4, iy + 16), (ix + 20, iy + 6), (ix + 36, iy + 16)], fill=INK, width=4)
    for k in range(4):
        xx = ix + 8 + k * 8
        d.line([(xx, iy + 18), (xx, iy + 34)], fill=INK, width=3)
    d.line([(ix + 2, iy + 37), (ix + 38, iy + 37)], fill=INK, width=4)
    d.text((140, 116), '법안톡', font=F('b', 38), fill=INK)
    d.text((272, 124), '· 60초 법안 요약', font=F('m', 30), fill=MUTED)

# ---------- content ----------
scenes = []
L = 80  # left margin

# S1 hook
s = Scene('s1', 4.6, 0)
s.add(chip_el('의료·보건', 34, fg=INK, bg=(110, 140, 255, 70)), L, 300, 0.1)
s.add(text_el(['사무장병원 잡는', [('“건보 특사경”', BLUE)], '8년 만에', '국회 문턱 넘을까?'], 96, 'bk', gap=1.24), L, 400, 0.35)
s.add(text_el(['사법경찰직무법 개정안 · 2026.11.26 기준'], 34, 'm', MUTED), L, 1000, 1.0)
s.add(chip_el('현재: 법사위 전체회의 의결 보류', 38, fg=(20, 12, 4), bg=ORANGE + (255,), padx=30, pady=16), L, 1100, 1.6, 'pop')
scenes.append(s)

# S2 what
s = Scene('s2', 7.2, 1)
s.add(text_el(['무슨 법안이야?'], 44, 'b', BLUE), L, 300, 0.1)
s.add(text_el(['건강보험공단 직원에게', [('특별사법경찰', ORANGE), (' 권한을', INK)], '주는 법이에요'], 76, 'bk', gap=1.3), L, 380, 0.4)
s.add(card_el(920, [('수사 대상', 32, 'm', MUTED), ('사무장병원·면허대여약국 등', 46, 'b', INK), ('불법 개설 의료기관', 46, 'b', INK)]), L, 760, 1.4)
s.add(card_el(920, [('핵심', 32, 'm', MUTED), ('지정된 공단 직원만 수사권', 46, 'b', INK), ('수사종결권은 없음', 46, 'b', INK)]), L, 1080, 2.4)
scenes.append(s)

# S3 pro
s = Scene('s3', 8.0, 2)
s.add(chip_el('찬성 · 건보공단·건보노조', 36, fg=(8, 30, 18), bg=GREEN + (255,), padx=28, pady=14), L, 300, 0.1)
s.add(text_el(['“수사가 너무 느려서', '돈이 새고 있다”'], 72, 'bk', gap=1.3), L, 400, 0.4)
s.add(card_el(920, [('2009~2025년 적발된 사무장병원', 32, 'm', MUTED), ('1,805곳', 84, 'bk', INK), ('건보 재정 피해 약 2조 9천억 원', 38, 'b', INK)]), L, 660, 1.3)
s.add(card_el(920, [('수사 기간 (공단 추산)', 32, 'm', MUTED), ('평균 11개월 → 3개월', 64, 'bk', INK), ('연 2천억 원 재정 누수 차단 기대', 38, 'b', INK)]), L, 1060, 2.6)
s.add(text_el(['* 노조·공단 측 주장 수치'], 28, 'r', MUTED), L, 1420, 3.2)
scenes.append(s)

# S4 con
s = Scene('s4', 7.6, 3)
s.add(chip_el('반대 · 의사협회·병원협회', 36, fg=(30, 8, 8), bg=(255, 120, 120, 255), padx=28, pady=14), L, 300, 0.1)
s.add(text_el(['“돈 주는 기관이', '수사까지? 과하다”'], 72, 'bk', gap=1.3), L, 400, 0.4)
s.add(card_el(920, [('이해충돌', 48, 'b', INK), ('진료비 지급·환수 기관이', 38, 'm', MUTED), ('강제수사권까지 갖게 됨', 38, 'm', MUTED)]), L, 660, 1.3)
s.add(card_el(920, [('수사권 남용 · 인권침해 우려', 48, 'b', INK), ('법무부도 “적법절차 통제장치 필요”', 38, 'm', MUTED)]), L, 1000, 2.4)
s.add(text_el(['공단 보완책: 외부 수사심의위원회 (최대 12명)'], 32, 'm', BLUE), L, 1290, 3.4)
scenes.append(s)

# S5 status timeline
s = Scene('s5', 10.0, 4)
s.add(text_el(['지금 어디까지 왔나?'], 64, 'bk'), L, 290, 0.1)
steps = [
    ('발의', '2018.12 첫 발의 · 20·21대 폐기 → 22대 재발의', 'done'),
    ('소관위 회부', '법제사법위원회', 'done'),
    ('법안심사소위', '11.11 통과 (8건 병합)', 'done'),
    ('법사위 전체회의', '11.16 의결 보류 · 11.18 처리 불발', 'now'),
    ('본회의', '표결', 'todo'),
    ('공포·시행', '', 'todo'),
]
TY0, TSTEP = 450, 170
TY0E = TY0 + 90
for i, (lab, sub, st) in enumerate(steps):
    col = INK if st != 'todo' else (120, 124, 133)
    lab_el = text_el([lab], 50 if st == 'now' else 46, 'bk' if st == 'now' else 'b', ORANGE if st == 'now' else col)
    s.add(lab_el, 190, TY0 + i * TSTEP - 8, 0.6 + i * 0.55)
    if sub:
        s.add(text_el([sub], 32, 'm', MUTED if st != 'now' else (255, 200, 160)), 190, TY0 + i * TSTEP + 62, 0.75 + i * 0.55)
    if st == 'now':
        s.add(chip_el('보류', 34, fg=(20, 12, 4), bg=ORANGE + (255,), padx=22, pady=10), 190 + lab_el.width + 20, TY0 + i * TSTEP - 2, 0.9 + i * 0.55, 'pop')

def timeline(c, d, t, out):
    def mix(col, a):
        return tuple(int(BG[k] + (col[k] - BG[k]) * a) for k in range(3))
    cx = 120
    for i, (lab, sub, st) in enumerate(steps):
        a = ease((t - (0.6 + i * 0.55)) / 0.4) * out
        if a <= 0:
            continue
        y = TY0E + i * TSTEP + 26
        if i < len(steps) - 1:
            nxt = ease((t - (0.9 + i * 0.55)) / 0.5)
            y2 = y + (TSTEP) * nxt
            lc = BLUE if st == 'done' else LINE
            d.line([(cx, y + 26), (cx, max(y + 26, y2 - 26))], fill=mix(lc, out), width=6)
        if st == 'done':
            d.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=mix(BLUE_D, a))
            d.line([(cx - 11, y), (cx - 3, y + 9), (cx + 12, y - 9)], fill=mix(INK, a), width=6)
        elif st == 'now':
            pulse = 0.5 + 0.5 * math.sin(t * 5)
            r = 24 + 14 * pulse
            d.ellipse((cx - r, y - r, cx + r, y + r), fill=mix((90, 45, 15), a))
            d.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=mix(ORANGE, a))
            d.rectangle((cx - 9, y - 11, cx - 3, y + 11), fill=mix(BG, a))
            d.rectangle((cx + 3, y - 11, cx + 9, y + 11), fill=mix(BG, a))
        else:
            d.ellipse((cx - 22, y - 22, cx + 22, y + 22), outline=mix((120, 124, 133), a), width=5)
s.custom.append(timeline)
scenes.append(s)

# S6 next + CTA
s = Scene('s6', 6.4, 5)
s.add(text_el(['다음은?'], 44, 'b', BLUE), L, 300, 0.1)
s.add(text_el(['같은 법률의 다른 기관', '특사경 개정안과 함께', [('다시 심사', ORANGE), ('할 예정', INK)]], 72, 'bk', gap=1.3), L, 380, 0.4)
s.add(text_el(['재논의 날짜는 아직 미정이에요'], 40, 'm', MUTED), L, 720, 1.2)

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
s.add(bell_btn(), L, 880, 1.9, 'pop')
s.add(text_el(['법사위 의결 · 본회의 표결 때 바로 알려드려요'], 34, 'm', MUTED), L, 1060, 2.4)
s.add(text_el(['출처: 코메디닷컴·팍스메디컬뉴스·데일리팜·', '서울경제·메디게이트뉴스 (2026.11 보도 종합)'], 28, 'r', (130, 134, 143), gap=1.45), L, 1300, 2.8)
scenes.append(s)

# ---------- render ----------
def render(sc):
    tmp = f'{OUT}/{sc.name}.tmp.mp4'
    fin = f'{OUT}/{sc.name}.mp4'
    n = int(round(sc.dur * FPS))
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(sc.frame(i / FPS).tobytes())
    p.stdin.close()
    if p.wait() == 0:
        os.replace(tmp, fin)

if __name__ == '__main__':
    if sys.argv[1] == 'preview':
        for sc, t in [(scenes[0], 3.0), (scenes[2], 5.0), (scenes[4], 7.0), (scenes[5], 4.5)]:
            sc.frame(t).save(f'{OUT}/prev_{sc.name}.png')
    else:
        for sc in scenes:
            if sys.argv[1] in ('all', sc.name):
                render(sc)
