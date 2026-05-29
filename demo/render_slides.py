"""Render demo-video slides (1920x1080) to demo/shots/*.png."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (13, 17, 23)          # github dark
PANEL = (22, 27, 34)
FG = (230, 237, 243)
MUTE = (139, 148, 158)
GREEN = (63, 185, 80)
ORANGE = (255, 123, 28)
RED = (248, 81, 73)
YELLOW = (210, 168, 60)
BLUE = (88, 166, 255)

SHOTS = Path(__file__).resolve().parent / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIALB = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
MENLO = "/System/Library/Fonts/Menlo.ttc"


def f(path, size):
    return ImageFont.truetype(path, size)


def canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def footer(d):
    d.text((80, H - 70), "github.com/CarrotGamesStudios/tos-compliance-agent",
            font=f(ARIAL, 30), fill=MUTE)
    d.text((W - 360, H - 70), "Apache-2.0  ·  open source", font=f(ARIAL, 30), fill=MUTE)


def save(img, name):
    img.save(SHOTS / name)
    print("wrote", name)


# 1 — title
img, d = canvas()
d.text((80, 300), "ToS / Compliance Agent", font=f(ARIALB, 92), fill=FG)
d.text((84, 430),
       "An AI agent that keeps your project continuously compliant —",
       font=f(ARIAL, 44), fill=FG)
d.text((84, 488),
       "it detects compliance drift, auto-fixes what it safely can,",
       font=f(ARIAL, 44), fill=FG)
d.text((84, 546), "and flags the rest — every finding cited to the source clause.",
       font=f(ARIAL, 44), fill=FG)
d.text((84, 660), "Built on Google Cloud", font=f(ARIALB, 40), fill=GREEN)
d.text((84, 720),
       "Vertex AI Agent Engine  ·  Agent Development Kit (ADK)  ·  Gemini 3.1 Pro  ·  Vertex AI RAG Engine",
       font=f(ARIAL, 34), fill=MUTE)
footer(d)
save(img, "01_title.png")

# 2 — problem
img, d = canvas()
d.text((80, 140), "The problem: compliance drift", font=f(ARIALB, 72), fill=FG)
d.text((80, 250), "Software silently falls out of compliance as it changes:",
       font=f(ARIAL, 42), fill=MUTE)
bullets = [
    "A new dependency adds a GPL/license conflict",
    "A PII field starts getting written to logs",
    "A third-party API's Terms of Service change upstream",
    "A new jurisdiction's privacy law starts to apply (GDPR, Colorado, ...)",
]
y = 380
for b in bullets:
    d.ellipse((86, y + 16, 104, y + 34), fill=ORANGE)
    d.text((130, y), b, font=f(ARIAL, 44), fill=FG)
    y += 90
d.text((80, y + 30), "Today it's caught late — in audits or incidents — if at all.",
       font=f(ARIALB, 44), fill=YELLOW)
footer(d)
save(img, "02_problem.png")

# 3 — subject
img, d = canvas()
d.text((80, 140), "Real-world test: VidSeeds", font=f(ARIALB, 72), fill=FG)
d.text((80, 250), "A production video-SEO app — the kind of codebase that drifts.",
       font=f(ARIAL, 42), fill=MUTE)
rows = [
    ("Publishes to", "YouTube · TikTok · Meta (Instagram/Facebook) · LinkedIn · X", BLUE),
    ("Handles", "user accounts & emails, Stripe payments, Postgres data", BLUE),
    ("Uses", "Google Gemini / Vertex AI, Google Analytics", BLUE),
]
y = 380
for label, val, col in rows:
    d.text((96, y), label, font=f(ARIALB, 40), fill=col)
    d.text((360, y), val, font=f(ARIAL, 40), fill=FG)
    y += 100
d.text((80, y + 30),
       "→ Exactly the license, privacy & platform-ToS rules our agent checks.",
       font=f(ARIALB, 42), fill=GREEN)
footer(d)
save(img, "03_subject.png")


# terminal helper
def terminal(name, title, lines):
    img, d = canvas()
    d.text((80, 90), title, font=f(ARIALB, 56), fill=FG)
    # window
    x0, y0, x1, y1 = 80, 200, W - 80, H - 130
    d.rounded_rectangle((x0, y0, x1, y1), radius=18, fill=(0, 0, 0))
    d.rounded_rectangle((x0, y0, x1, y0 + 54), radius=18, fill=(40, 44, 52))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse((x0 + 26 + i * 34, y0 + 18, x0 + 44 + i * 34, y0 + 36), fill=c)
    mono = f(MENLO, 30)
    y = y0 + 90
    for text, color in lines:
        d.text((x0 + 36, y), text, font=mono, fill=color)
        y += 42
    footer(d)
    save(img, name)


# 4 — scan (real output)
terminal(
    "04_scan.png",
    "Scan the project — deterministic checks + a Gemini judge",
    [
        ("$ compliance-agent scan . --judge", GREEN),
        ("", FG),
        ("# Compliance Report", FG),
        ("**2 violation(s)**", FG),
        ("", FG),
        ("[HIGH]   privacy / priv-pii-in-logs              (GDPR Art.5(1)(f))", RED),
        ("  73 PII-in-log sites across 31 files: email, secret, api_key, ...", MUTE),
        ("  e.g. lib/email/resend-service.ts, lib/auth/better-auth.ts", MUTE),
        ("", FG),
        ("[MEDIUM] license / lic-apache-notice            (Apache-2.0 §4)", YELLOW),
        ("  14 Apache-2.0 deps missing NOTICE attribution:", MUTE),
        ("  @aws-sdk/client-s3, @google/genai, openai, sharp, drizzle-orm ...", MUTE),
        ("", FG),
        ("USA / Colorado / EU / YouTube-ToS obligations evaluated by Gemini →", BLUE),
        ("judged compliant from the available evidence (flagged if uncertain).", BLUE),
    ],
)

# 5 — fix (real output)
terminal(
    "05_fix.png",
    "Auto-fix the deterministic issues",
    [
        ("$ compliance-agent fix . --apply", GREEN),
        ("Fixed lic-apache-notice -> /Users/.../VidSeeds2.0/NOTICE", FG),
        ("", FG),
        ("$ cat NOTICE", GREEN),
        ("NOTICE", FG),
        ("This product includes third-party software:", MUTE),
        ("- @aws-sdk/client-s3 (Apache-2.0)", FG),
        ("- @google/genai (Apache-2.0)", FG),
        ("- openai (Apache-2.0)", FG),
        ("- drizzle-orm (Apache-2.0)   ... (14 total)", FG),
        ("", FG),
        ("$ compliance-agent scan .            # re-scan", GREEN),
        ("✓ lic-apache-notice resolved", GREEN),
        ("  (PII-in-logs remains — flagged for the developer to redact)", MUTE),
    ],
)

# 6 — how it works
img, d = canvas()
d.text((80, 120), "How it works", font=f(ARIALB, 72), fill=FG)
steps = [
    ("1", "Compile", "Source docs (ToS, laws, licenses, contracts) → versioned Policy Packs."),
    ("2", "Verify", "Every obligation's clause must be found verbatim in the source, or it's dropped."),
    ("3", "Scan", "Build a fact model of the repo: licenses (SBOM), PII-in-logs, imports, platform APIs."),
    ("4", "Judge", "Deterministic analyzers + Gemini for gray areas → findings with citations."),
    ("5", "Fix", "Auto-fix the safe ones; flag the rest."),
]
y = 250
for n, head, body in steps:
    d.ellipse((90, y, 142, y + 52), outline=GREEN, width=4)
    d.text((106, y + 6), n, font=f(ARIALB, 36), fill=GREEN)
    d.text((176, y), head, font=f(ARIALB, 40), fill=FG)
    d.text((176, y + 50), body, font=f(ARIAL, 32), fill=MUTE)
    y += 130
d.text((80, y + 10),
       "Two-axis drift detection: your CODE changes  +  the upstream DOCUMENTS change.",
       font=f(ARIALB, 38), fill=ORANGE)
footer(d)
save(img, "06_how.png")

# 7 — CTA
img, d = canvas()
d.text((80, 320), "Install it. Scan in 60 seconds.", font=f(ARIALB, 80), fill=FG)
d.text((84, 470), "pip install 'compliance-agent[gcp]'", font=f(MENLO, 46), fill=GREEN)
d.text((84, 545), "compliance-agent scan .   # local, no cloud needed", font=f(MENLO, 40), fill=MUTE)
d.text((84, 660), "Single-tenant: deploys into YOUR Google Cloud project.",
       font=f(ARIAL, 40), fill=FG)
d.text((84, 720), "Your confidential docs & contracts never leave it.",
       font=f(ARIAL, 40), fill=FG)
footer(d)
save(img, "07_cta.png")

print("done")
