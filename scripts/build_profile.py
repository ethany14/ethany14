#!/usr/bin/env python3
"""Build the profile cards in assets/ from data/stats.json.

Each card is a self-contained SVG: text stays real text, set in Barlow subset
and embedded as WOFF so it renders sharply inside GitHub's <img> tags, and the
motion is CSS or SMIL, which GitHub plays in README images. The layout is
designed at 1200 units for the ~830 px README column, so no text falls below
about 12 px on screen.

Usage: python scripts/build_profile.py   (needs fonttools)"""
import base64
import datetime as dt
import io
import json
import math
import random
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"
ASSETS = ROOT / "assets"
DATA = ROOT / "data" / "stats.json"

BLACK = "#000000"
WHITE = "#ffffff"
SOFT = "#d4d4d4"       # body copy
GREY = "#a8a8a8"       # labels
RULE = "#2a2a2a"
EDGE = "#1f1f1f"
SKY = "#3d8bff"
GO = "#3ddc84"

FULL_W = 1200
PAIR_W, PAIR_GAP = 600, 12
RADIUS = 24

TOOLS = [
    ("LANGUAGES & DATA", ["PYTHON", "SQL", "JAVASCRIPT", "NODE.JS", "REACT", "PYSPARK", "SQLITE", "TABLEAU"]),
    ("AI & AGENTS", ["PYTORCH", "LANGCHAIN", "LANGGRAPH", "MCP", "AGENT ORCHESTRATION", "TOOL USE", "LLM APIS"]),
    ("RETRIEVAL & EVALS", ["RAG", "HYBRID RETRIEVAL", "BM25 + BGE EMBEDDINGS", "HUMAN + AUTOMATED EVALS",
                           "SAFETY GUARDRAILS"]),
    ("BACKEND & TOOLING", ["FASTAPI", "REST APIS", "PYDANTIC", "SQLALCHEMY", "PLAYWRIGHT", "ASYNCIO", "DOCKER", "GIT",
                           "PYTEST"]),
    ("AI-ASSISTED DEV", ["CLAUDE CODE", "CODEX", "CURSOR", "GITHUB COPILOT"]),
]

INTRO = ("I build AI agents that do real work and keep the receipts. Every claim they make is checked against "
         "evidence before it reaches a person, and the final call always stays with a human.")


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------- fonts
class Face:
    def __init__(self, family, filename):
        self.family = family
        self.path = FONTS / filename
        font = TTFont(self.path)
        self.cmap = font.getBestCmap()
        self.hmtx = font["hmtx"]
        self.upm = font["head"].unitsPerEm

    def width(self, text, size, spacing=0.0):
        adv = sum(self.hmtx[self.cmap.get(ord(c), self.cmap[ord("?")])][0] for c in text)
        return adv * size / self.upm + spacing * len(text)

    def face_css(self, chars):
        opts = subset.Options()
        opts.flavor = "woff"
        opts.layout_features = ["kern"]
        opts.name_IDs = ["*"]
        font = TTFont(self.path)
        sub = subset.Subsetter(opts)
        sub.populate(text="".join(sorted(chars)))
        sub.subset(font)
        buf = io.BytesIO()
        font.flavor = "woff"
        font.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        return f"@font-face{{font-family:{self.family};src:url(data:font/woff;base64,{data}) format('woff')}}"


LIGHT = Face("BL", "Barlow-Light.ttf")
REG = Face("BR", "Barlow-Regular.ttf")
MED = Face("BM", "Barlow-Medium.ttf")
SEMI = Face("BS", "Barlow-SemiBold.ttf")


class Doc:
    """Collects one SVG: body markup, CSS and the characters each face needs."""

    def __init__(self, uid):
        self.uid = uid
        self.css = []
        self.used = {}

    def text(self, s, x, y, size, face=REG, fill=WHITE, spacing=0.0, anchor="start", attrs=""):
        self.used.setdefault(face, set()).update(s)
        a = f' text-anchor="{anchor}"' if anchor != "start" else ""
        ls = f' letter-spacing="{fmt(spacing)}"' if spacing else ""
        return (f'<text x="{fmt(x)}" y="{fmt(y)}" font-family="{face.family}" font-size="{fmt(size)}"{ls} '
                f'fill="{fill}"{a}{attrs}>{escape(s)}</text>')

    def render(self, w, h, body, label):
        fonts = "".join(face.face_css(chars) for face, chars in self.used.items())
        css = fonts + "".join(self.css) + "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" width="{fmt(w)}" '
                f'height="{fmt(h)}" role="img" aria-label={quoteattr(label)}>\n<style>{css}</style>\n{body}\n</svg>\n')


def card(doc, body, w, h, label, offset=0, total_w=None):
    """Round-cornered black card; offset leaves room for the gap beside a paired card."""
    total_w = total_w or w
    clip = f"clip{doc.uid}"
    return doc.render(total_w, h,
                      f'<defs><clipPath id="{clip}"><rect x="{offset}" width="{w}" height="{fmt(h)}" rx="{RADIUS}"/></clipPath></defs>'
                      f'<g clip-path="url(#{clip})"><g transform="translate({offset} 0)">'
                      f'<rect width="{w}" height="{fmt(h)}" fill="{BLACK}"/>{body}</g></g>'
                      f'<rect x="{offset + 0.75}" y="0.75" width="{w - 1.5}" height="{fmt(h - 1.5)}" rx="{RADIUS}" '
                      f'fill="none" stroke="{EDGE}" stroke-width="1.5"/>', label)


def pair(doc, body, h, label, left):
    return card(doc, body, PAIR_W, h, label, offset=0 if left else PAIR_GAP, total_w=PAIR_W + PAIR_GAP)


# ---------------------------------------------------------------- shared pieces
def stars(rng, n, w, h, twinkle=0):
    out = []
    for i in range(n):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        r = rng.choice([0.6, 0.8, 1.0, 1.3])
        o = rng.uniform(0.2, 0.75)
        cls = ""
        if i < twinkle:
            r = 1.4
            cls = f' class="tw" style="animation-delay:{rng.uniform(0, 4):.2f}s"'
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{WHITE}" opacity="{o:.2f}"{cls}/>')
    return "".join(out)


TWINKLE_CSS = ".tw{animation:tw 4s ease-in-out infinite}@keyframes tw{0%,100%{opacity:.15}50%{opacity:1}}"
PULSE_CSS = (".pulse{animation:pulse 2s ease-out infinite;transform-box:fill-box;transform-origin:center}"
             "@keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(3.2);opacity:0}}")


def status_dot(x, y, color=GO):
    return (f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="5" fill="{color}" class="pulse"/>'
            f'<circle cx="{fmt(x)}" cy="{fmt(y)}" r="5" fill="{color}"/>')


def up_arrow(x, y, color, k=15):
    return (f'<path d="M{fmt(x)} {fmt(y + k)}L{fmt(x + k)} {fmt(y)}M{fmt(x + 3)} {fmt(y)}H{fmt(x + k)}V{fmt(y + k - 3)}" '
            f'fill="none" stroke="{color}" stroke-width="2.4" stroke-linecap="square"/>')


def button(doc, label, x, y, w, h=76):
    """Solid white call-to-action with a light sweep and a nudging arrow."""
    size, spacing = 21, 4.5
    tw = SEMI.width(label, size, spacing) - spacing
    tx = x + (w - tw - 34) / 2
    clip = f"btn{doc.uid}"
    doc.css.append(".sweep{animation:sweep 4.5s cubic-bezier(.4,0,.2,1) infinite}"
                   "@keyframes sweep{0%{transform:translateX(0)}45%,100%{transform:translateX(760px)}}"
                   ".nudge{animation:nudge 4.5s ease-in-out infinite}"
                   "@keyframes nudge{0%,40%,70%,100%{transform:translate(0,0)}55%{transform:translate(4px,-4px)}}")
    return (f'<defs><clipPath id="{clip}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{h}" rx="8"/></clipPath>'
            f'<linearGradient id="sh{doc.uid}" x1="0" x2="1"><stop offset="0" stop-color="#bcd6ff" stop-opacity="0"/>'
            f'<stop offset="0.5" stop-color="#bcd6ff" stop-opacity="0.75"/><stop offset="1" stop-color="#bcd6ff" stop-opacity="0"/>'
            f'</linearGradient></defs>'
            f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{h}" rx="8" fill="{WHITE}"/>'
            f'<g clip-path="url(#{clip})"><g class="sweep"><rect x="{fmt(x - 140)}" y="{fmt(y - 10)}" width="90" '
            f'height="{h + 20}" fill="url(#sh{doc.uid})" transform="skewX(-20)"/></g></g>'
            + doc.text(label, tx, y + h / 2 + 7.5, size, SEMI, BLACK, spacing)
            + f'<g class="nudge">{up_arrow(tx + tw + 18, y + h / 2 - 8, BLACK)}</g>')


def fit(face, text, size, spacing, max_w):
    while face.width(text, size, spacing) > max_w and size > 10:
        size -= 0.5
    return size


def short_date(iso):
    return dt.datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%b %d, %Y").upper()


# ---------------------------------------------------------------- hero card
def rolling_number(doc, value, cx, baseline, size, delay):
    """Odometer: each digit rolls up to its value when the image loads. The
    resting position is the final value, so without animation it still reads right."""
    if value is None:
        return doc.text("--", cx, baseline, size, LIGHT, WHITE, anchor="middle")
    s = f"{value:02d}"
    cell = max(LIGHT.width(d, size) for d in "0123456789")
    gap = size * 0.06
    total = len(s) * cell + (len(s) - 1) * gap
    x0 = cx - total / 2
    line = size * 1.15
    clip = f"roll{doc.uid}_{int(cx)}"
    out = [f'<defs><clipPath id="{clip}"><rect x="{fmt(x0 - 6)}" y="{fmt(baseline - size * 0.82)}" '
           f'width="{fmt(total + 12)}" height="{fmt(size * 0.98)}"/></clipPath></defs><g clip-path="url(#{clip})">']
    for i, ch in enumerate(s):
        target = int(ch)
        seq = list(range(target, -1, -1)) + list(range(9, -1, -1))   # top to bottom
        shift = (len(seq) - 1) * line
        name = f"r{doc.uid}{int(cx)}{i}"
        doc.css.append(f".{name}{{animation:{name} {1.8 + 0.35 * i:.2f}s cubic-bezier(.15,.7,.2,1) {delay:.2f}s both}}"
                       f"@keyframes {name}{{from{{transform:translateY(-{fmt(shift)}px)}}to{{transform:translateY(0)}}}}")
        dx = x0 + i * (cell + gap) + cell / 2
        out.append(f'<g class="{name}">' + "".join(doc.text(str(d), dx, baseline + k * line, size, LIGHT, WHITE, anchor="middle")
                                            for k, d in enumerate(seq)) + "</g>")
    out.append("</g>")
    return "".join(out)


def hero_card(stats):
    doc = Doc("hero")
    W, HERO_H = FULL_W, 520
    rng = random.Random(9)
    R, CX, CY = 1500, 760, 1880
    limb_y = lambda x: CY - math.sqrt(R * R - (x - CX) ** 2)
    created = dt.datetime.strptime(stats["account_created"][:10], "%Y-%m-%d").date()
    today = dt.datetime.strptime(stats["generated_at"][:10], "%Y-%m-%d").date()
    mission_day = (today - created).days

    doc.css += [TWINKLE_CSS, PULSE_CSS,
                ".atmo{animation:atmo 7s ease-in-out infinite}@keyframes atmo{0%,100%{opacity:.8}50%{opacity:1}}",
                ".caret{animation:caret 1.1s steps(1) infinite}@keyframes caret{50%{opacity:0}}"]
    b = [f'<defs>'
         f'<radialGradient id="atmo" cx="{CX}" cy="{CY}" r="{R + 60}" gradientUnits="userSpaceOnUse">'
         f'<stop offset="0.955" stop-color="{SKY}" stop-opacity="0"/><stop offset="0.962" stop-color="{SKY}" stop-opacity="0.9"/>'
         f'<stop offset="0.975" stop-color="#7fb6ff" stop-opacity="0.35"/><stop offset="1" stop-color="{SKY}" stop-opacity="0"/></radialGradient>'
         f'<linearGradient id="earth" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0d1a2e"/>'
         f'<stop offset="0.08" stop-color="#05080f"/><stop offset="1" stop-color="{BLACK}"/></linearGradient>'
         f'<radialGradient id="sun" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{WHITE}" stop-opacity="0.95"/>'
         f'<stop offset="0.25" stop-color="#cfe3ff" stop-opacity="0.45"/><stop offset="1" stop-color="{SKY}" stop-opacity="0"/></radialGradient>'
         f'<radialGradient id="dot" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{WHITE}"/>'
         f'<stop offset="1" stop-color="{WHITE}" stop-opacity="0"/></radialGradient>'
         f'<clipPath id="scene"><rect width="{W}" height="{HERO_H}"/></clipPath></defs><g clip-path="url(#scene)">',
         stars(rng, 170, W, 400, twinkle=26),
         f'<circle class="atmo" cx="{CX}" cy="{CY}" r="{R + 60}" fill="url(#atmo)"/>',
         f'<circle cx="{CX}" cy="{CY}" r="{R}" fill="url(#earth)"/>',
         f'<ellipse class="atmo" cx="1090" cy="{fmt(limb_y(1090))}" rx="230" ry="26" fill="url(#sun)" '
         f'transform="rotate(8 1090 {fmt(limb_y(1090))})"/>']

    # Ascent: the trail draws itself while the craft climbs, then both fade and relaunch.
    x0, y0 = 590, limb_y(590)
    ascent = f"M{x0} {fmt(y0)} C 640 300 760 200 930 150"
    pts = [(x0, y0), (640, 300), (760, 200), (930, 150)]
    length = sum(math.dist(_bez(pts, i / 200), _bez(pts, (i + 1) / 200)) for i in range(200))
    timing = 'dur="9s" repeatCount="indefinite" keyTimes="0;0.62;1" calcMode="spline" keySplines=".3 .1 .25 1;0 0 1 1"'
    fade = 'values="1;1;0;0" keyTimes="0;0.7;0.86;1" dur="9s" repeatCount="indefinite"'
    b.append(f'<path d="{ascent}" fill="none" stroke="{WHITE}" stroke-opacity="0.12" stroke-width="1.5"/>')
    b.append(f'<path d="{ascent}" fill="none" stroke="{WHITE}" stroke-width="2.2" stroke-dasharray="{fmt(length)} {fmt(length)}" '
             f'stroke-dashoffset="0"><animate attributeName="stroke-dashoffset" values="{fmt(length)};0;0" {timing}/>'
             f'<animate attributeName="opacity" {fade}/></path>')
    b.append(f'<g><circle r="18" fill="url(#dot)"/><circle r="3.5" fill="{WHITE}"/>'
             f'<animateMotion path="{ascent}" keyPoints="0;1;1" {timing}/><animate attributeName="opacity" {fade}/></g>')
    b.append(f'<path d="M930 150 C 1010 128 1090 120 1200 122" fill="none" stroke="{WHITE}" stroke-opacity="0.35" '
             f'stroke-width="1.5" stroke-dasharray="4 8"/>')
    b.append(doc.text(f"MISSION DAY {mission_day:,}", 972, 112, 17, MED, WHITE, 3.5))
    b.append(status_dot(978, 135) + doc.text("ORBIT NOMINAL", 992, 141, 15, MED, GREY, 3.5))

    # Identity.
    b.append(doc.text("ETHANY14  /  GITHUB", 72, 128, 18, MED, GREY, 6))
    b.append(doc.text("ETHAN YU", 66, 222, 94, SEMI, WHITE, 14))
    b.append(doc.text("AI ENGINEER", 72, 272, 27, REG, WHITE, 7))
    b.append(f'<path d="M72 296H392" stroke="{WHITE}" stroke-width="1.5"/>')
    tag = "BUILDING AGENTS THAT SHOW THEIR WORK"
    b.append(doc.text(tag, 72, 332, 19, REG, SOFT, 4.5))
    b.append(f'<rect class="caret" x="{fmt(72 + REG.width(tag, 19, 4.5) + 4)}" y="316" width="11" height="19" fill="{WHITE}"/>')

    b.append("</g>")

    # Stats strip with odometer numbers.
    y = HERO_H
    b.append(f'<path d="M0 {y}H{W}" stroke="{RULE}" stroke-width="1.5"/>')
    items = [(stats.get("total_stars"), "STARS EARNED"),
             (stats.get("contributions"), f"CONTRIBUTIONS IN {stats['year']}"),
             (sum(len(t) for _, t in TOOLS), "TOOLS IN STACK")]
    col = W / len(items)
    for i, (value, label) in enumerate(items):
        cx = col * i + col / 2
        b.append(rolling_number(doc, value, cx, y + 118, 92, 0.2 + 0.25 * i))
        b.append(doc.text(label, cx, y + 160, 17, MED, GREY, 6, anchor="middle"))
        if i:
            b.append(f'<path d="M{fmt(col * i)} {y + 46}V{y + 160}" stroke="{RULE}" stroke-width="1.5"/>')
    y += 210
    b.append(f'<path d="M0 {y}H{W}" stroke="{RULE}" stroke-width="1.5"/>')

    # Intro paragraph.
    y += 62
    size, line, spacing = 25, 40, 0.4
    words, cur = INTRO.split(), ""
    for word in words:
        cand = f"{cur} {word}".strip()
        if REG.width(cand, size, spacing) > W - 80 and cur:
            b.append(doc.text(cur, 40, y, size, REG, SOFT, spacing))
            y += line
            cur = word
        else:
            cur = cand
    b.append(doc.text(cur, 40, y, size, REG, SOFT, spacing))
    H = y + 44
    label = (f"Ethan Yu, AI engineer, building agents that show their work. {stats.get('total_stars')} stars earned, "
             f"{stats.get('contributions') or 'no'} contributions in {stats['year']}, "
             f"{sum(len(t) for _, t in TOOLS)} tools in stack. {INTRO}")
    return card(doc, "".join(b), W, H, label)


def _bez(p, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = p
    u = 1 - t
    return (u ** 3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t ** 3 * x3,
            u ** 3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t ** 3 * y3)


# ---------------------------------------------------------------- contact buttons
def contact_card(uid, kicker, label, alt, left):
    doc = Doc(uid)
    W, H = PAIR_W, 196
    body = doc.text(kicker, 40, 60, 17, MED, GREY, 6) + button(doc, label, 40, 86, W - 80)
    return pair(doc, body, H, alt, left)


# ---------------------------------------------------------------- mission cards
def holly_art(doc):
    # Eregion's holly with a satellite on a tilted orbit.
    orbit = "M150 165 A150 46 0 1 1 450 165 A150 46 0 1 1 150 165"
    return (f'<g transform="rotate(-14 300 165)"><path d="{orbit}" fill="none" stroke="{WHITE}" stroke-opacity="0.35" '
            f'stroke-width="1.5" stroke-dasharray="3 7"/><g><circle r="12" fill="url(#glow{doc.uid})"/>'
            f'<circle r="3.5" fill="{WHITE}"/><animateMotion path="{orbit}" dur="10s" repeatCount="indefinite"/></g></g>'
            f'<g transform="translate(222 82) scale(5)"><g fill="none" stroke="{WHITE}" stroke-width="0.9" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M15 17C13.6 14.8 10.6 15 9.6 12.8 7.6 13.4 6 11.6 4.4 12.4 5.6 9.8 3.8 8.2 5 6.6 7 7.4 8.4 5.4 10.6 6.6 11 4.4 13.4 4 14.6 5.4 14 8 16.2 9.6 15.6 12.2S16.8 14.2 15 17Z"/>'
            '<path d="M15 17 7 8.6"/><path d="M17 17c2.2-1.2 2.4-4.2 4.6-5-.4-2 1.4-3.4.8-5 2.4 1.4 4.2-.2 5.6 1.2-.8 1.9 1.2 3.4 0 5.4 2 .6 2.2 3 .8 4-2.4-.8-4.2 1.2-6.6.4-1.8 1.2-3.6-.2-5.2-1z"/>'
            '<path d="M17 17l8.6-7"/><circle cx="13.2" cy="22" r="2.3"/><circle cx="18.2" cy="22.6" r="2.3"/>'
            '<circle cx="15.8" cy="26.6" r="2.3"/></g></g>')


def radar_art(doc):
    c, cy, r = 300, 165, 78
    wedge = (f"M{c} {cy}L{fmt(c + r)} {cy}A{r} {r} 0 0 0 {fmt(c + r * math.cos(math.radians(-55)))} "
             f"{fmt(cy + r * math.sin(math.radians(-55)))}Z")
    out = [f'<defs><linearGradient id="sweep{doc.uid}" x1="1" y1="0.5" x2="0.3" y2="0">'
           f'<stop offset="0" stop-color="{WHITE}" stop-opacity="0.45"/><stop offset="1" stop-color="{WHITE}" stop-opacity="0"/>'
           f'</linearGradient></defs>',
           f'<path d="{wedge}" fill="url(#sweep{doc.uid})"><animateTransform attributeName="transform" type="rotate" '
           f'from="0 {c} {cy}" to="360 {c} {cy}" dur="4s" repeatCount="indefinite"/></path>',
           f'<circle cx="{c}" cy="{cy}" r="{r}" fill="none" stroke="{WHITE}" stroke-width="1.6"/>',
           f'<circle cx="{c}" cy="{cy}" r="44" fill="none" stroke="{WHITE}" stroke-opacity="0.5" stroke-width="1.2" stroke-dasharray="3 6"/>']
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        out.append(f'<path d="M{c + dx * 58} {cy + dy * 58}L{c + dx * 110} {cy + dy * 110}" stroke="{WHITE}" stroke-width="1.6"/>')
    for a in range(0, 360, 15):
        r2 = 84 if a % 45 else 90
        t = math.radians(a)
        out.append(f'<path d="M{fmt(c + r * math.cos(t))} {fmt(cy + r * math.sin(t))}L{fmt(c + r2 * math.cos(t))} '
                   f'{fmt(cy + r2 * math.sin(t))}" stroke="{WHITE}" stroke-opacity="0.7" stroke-width="1.2"/>')
    # A contact that lights up each time the sweep passes over it.
    bx, by = c + 46, cy - 30
    out.append(f'<circle cx="{bx}" cy="{by}" r="4" fill="{GO}" opacity="0"><animate attributeName="opacity" '
               f'values="0;0;1;0" keyTimes="0;0.86;0.9;1" dur="4s" repeatCount="indefinite"/></circle>')
    out.append(f'<circle cx="{c}" cy="{cy}" r="3.5" fill="{WHITE}"/>')
    return "".join(out)


def mission_card(uid, index, name, kind, art_fn, rows, left):
    doc = Doc(uid)
    doc.css += [TWINKLE_CSS, PULSE_CSS]
    W, TOP, PAD = PAIR_W, 330, 40
    b = [f'<defs><radialGradient id="bg{uid}" cx="0.5" cy="0.62" r="0.6"><stop offset="0" stop-color="#16263f"/>'
         f'<stop offset="1" stop-color="{BLACK}"/></radialGradient>'
         f'<radialGradient id="glow{uid}" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="{WHITE}" stop-opacity="0.9"/>'
         f'<stop offset="1" stop-color="{WHITE}" stop-opacity="0"/></radialGradient></defs>',
         f'<rect width="{W}" height="{TOP}" fill="url(#bg{uid})"/>', stars(random.Random(uid), 60, W, TOP, twinkle=10),
         art_fn(doc),
         doc.text(f"MISSION {index}", PAD, 56, 17, MED, GREY, 6),
         doc.text("ACTIVE", W - PAD, 56, 17, MED, WHITE, 5, anchor="end"),
         status_dot(W - PAD - MED.width("ACTIVE", 17, 5) - 10, 50),
         doc.text("OVERVIEW", PAD, TOP + 56, 17, MED, GREY, 6)]
    size = fit(SEMI, kind, 38, 6, W - 2 * PAD)
    b.append(doc.text(kind, PAD, TOP + 104, size, SEMI, WHITE, 6))
    y = TOP + 140
    for label, value in rows:
        b.append(f'<path d="M{PAD} {y}H{W - PAD}" stroke="{RULE}" stroke-width="1.5"/>')
        b.append(doc.text(label, PAD, y + 40, 17, MED, WHITE, 4.5))
        vsize = fit(REG, value, 18, 2.5, W - 2 * PAD - MED.width(label, 17, 4.5) - 24)
        b.append(doc.text(value, W - PAD, y + 40, vsize, REG, SOFT, 2.5, anchor="end"))
        y += 62
    b.append(f'<path d="M{PAD} {y}H{W - PAD}" stroke="{RULE}" stroke-width="1.5"/>')
    b.append(button(doc, "VIEW REPOSITORY", PAD, y + 40, W - 2 * PAD))
    H = y + 40 + 76 + 44
    alt = (f"Mission {index}, {name}, {kind.lower()}: " + "; ".join(f"{l.lower()} {v.lower()}" for l, v in rows)
           + ". View repository.")
    return pair(doc, "".join(b), H, alt, left)


# ---------------------------------------------------------------- stack and education
def heading(doc, kicker, title):
    b = [doc.text(kicker, 40, 62, 17, MED, GREY, 6), doc.text(title, 40, 108, 38, SEMI, WHITE, 10)]
    tw = SEMI.width(title, 38, 10)
    b.append(f'<path d="M{fmt(40 + tw + 26)} 95H{FULL_W - 40}" stroke="{RULE}" stroke-width="1.5"/>')
    return "".join(b), 140


def stack_card():
    doc = Doc("stack")
    W, PAD, LABEL_W, SIZE, LINE, SEP = FULL_W, 40, 360, 20, 36, "  /  "
    # Systems check: each lamp lights in turn, holds, and the sequence repeats.
    doc.css.append(".lamp{animation:lamp 8s ease-out infinite}"
                   "@keyframes lamp{0%{fill:#2a2a2a}6%,88%{fill:" + GO + "}100%{fill:#2a2a2a}}")
    body, y = heading(doc, "TECH STACK", "VEHICLE SYSTEMS")
    b = [body]
    x0, x1 = PAD + LABEL_W, W - PAD
    for i, (label, items) in enumerate(TOOLS):
        lines, cur = [], ""
        for it in items:
            cand = it if not cur else cur + SEP + it
            if REG.width(cand, SIZE, 2) > x1 - x0 and cur:
                lines.append(cur)
                cur = it
            else:
                cur = cand
        lines.append(cur)
        b.append(f'<path d="M{PAD} {y}H{W - PAD}" stroke="{RULE}" stroke-width="1.5"/>')
        b.append(f'<circle class="lamp" style="animation-delay:{0.35 * i:.2f}s" cx="{PAD + 5}" cy="{y + 42}" r="5" fill="{GO}"/>')
        b.append(doc.text(label, PAD + 22, y + 48, 18, MED, WHITE, 4.5))
        for k, ln in enumerate(lines):
            b.append(doc.text(ln, x0, y + 48 + k * LINE, SIZE, REG, SOFT, 2))
        y += 40 + LINE * len(lines)
    b.append(f'<path d="M{PAD} {y}H{W - PAD}" stroke="{RULE}" stroke-width="1.5"/>')
    H = y + 36
    alt = "Tech stack. " + " ".join(f"{l.title()}: {', '.join(i)}." for l, i in TOOLS)
    return card(doc, "".join(b), W, H, alt)


def education_card(stats):
    doc = Doc("edu")
    doc.css.append(PULSE_CSS)
    W, PAD = FULL_W, 40
    body, y = heading(doc, "CREW TRAINING", "EDUCATION")
    b = [body]
    for left, right in (("CORNELL UNIVERSITY", "M.ENG., SYSTEMS ENGINEERING"),
                        ("UNIVERSITY OF WISCONSIN–MADISON", "B.A., COMPUTER SCIENCE")):
        b.append(f'<path d="M{PAD} {y}H{W - PAD}" stroke="{RULE}" stroke-width="1.5"/>')
        b.append(doc.text(left, PAD, y + 52, 19, MED, WHITE, 4.5))
        b.append(doc.text(right, W - PAD, y + 52, 19, REG, SOFT, 2.5, anchor="end"))
        y += 84
    b.append(f'<path d="M{PAD} {y}H{W - PAD}" stroke="{RULE}" stroke-width="1.5"/>')
    y += 76
    b.append(doc.text("ETHANY14 © 2026", PAD, y, 16, MED, GREY, 5))
    sync = f"LAST SYNC {stats['generated_at'][:10]} UTC"
    b.append(doc.text(sync, W - PAD, y, 16, MED, GREY, 5, anchor="end"))
    b.append(status_dot(W - PAD - MED.width(sync, 16, 5) - 12, y - 6))
    H = y + 44
    return card(doc, "".join(b), W, H,
                "Education: Cornell University, M.Eng. Systems Engineering. University of Wisconsin–Madison, "
                "B.A. Computer Science.")


# ---------------------------------------------------------------- main
def main():
    stats = json.loads(DATA.read_text())

    def repo_rows(name, kind_rows):
        repo = stats.get("repos", {}).get(name, {})
        rows = list(kind_rows)
        if "stars" in repo:
            rows.append(("STARS", f"{repo['stars']:,}"))
        if "pushed_at" in repo:
            rows.append(("LAST PUSH", short_date(repo["pushed_at"])))
        return rows

    cards = {
        "card-hero.svg": hero_card(stats),
        "btn-linkedin.svg": contact_card("li", "LINKEDIN", "CONNECT ON LINKEDIN", "Connect on LinkedIn", True),
        "btn-email.svg": contact_card("em", "EMAIL", "YZYRTK@GMAIL.COM", "Email yzyrtk@gmail.com", False),
        "card-eregion.svg": mission_card("er", "01", "Eregion", "AI CAREER COPILOT", holly_art, repo_rows(
            "Eregion-Job-Finding-Agent", [("TYPE", "JOB SEARCH, TAILORING, APPLYING"),
                                          ("STACK", "PYTHON / FASTAPI / PLAYWRIGHT"),
                                          ("CONTROL", "HUMAN APPROVES EVERY SUBMIT")]), True),
        "card-roundcrafter.svg": mission_card("rc", "02", "RoundCrafter", "CS2 ANALYSIS AGENT", radar_art, repo_rows(
            "Cs2-Roundcrafter", [("TYPE", "REPLAY ANALYSIS + COACHING"),
                                 ("STACK", "PYTHON / PYTORCH / HYBRID RAG"),
                                 ("CONTROL", "EVERY FINDING CITES EVIDENCE")]), False),
        "card-stack.svg": stack_card(),
        "card-education.svg": education_card(stats),
    }
    ASSETS.mkdir(exist_ok=True)
    for name, text in cards.items():
        (ASSETS / name).write_text(text)
        print(f"{name:24} {len(text) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
