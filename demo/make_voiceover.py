"""Generate per-scene ElevenLabs voiceover MP3s for the demo video."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

VOICE_ID = "cjVigY5qzO86Huf0OWal"  # Eric - Smooth, Trustworthy
MODEL = "eleven_multilingual_v2"
OUT = Path(__file__).resolve().parent / "audio"
OUT.mkdir(parents=True, exist_ok=True)


def load_key() -> str:
    for line in open("/Users/akiparuk/Downloads/VidSeeds2.0/.env.local"):
        m = re.match(r"\s*ELEVENLABS_API_KEY\s*=\s*(.+)", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("ELEVENLABS_API_KEY not found")


SCENES = [
    ("01", "The Terms-of-Service and Compliance Agent is an open-source A.I. agent, built on "
           "Google Cloud, that keeps your project continuously compliant. It catches compliance "
           "drift, auto-fixes what it safely can, and flags the rest — every finding cited to the "
           "exact source clause."),
    ("02", "Here's the problem. Software silently drifts out of compliance. A new dependency adds a "
           "license conflict. A personal-data field starts landing in your logs. A third-party A.P.I. "
           "changes its Terms. A new privacy law starts to apply. Today, you find out in an audit, or "
           "an incident."),
    ("03", "To prove it works, we pointed it at VidSeeds — a real production video-S.E.O. app. It "
           "publishes to YouTube, TikTok, Meta, LinkedIn and X, takes Stripe payments, and stores "
           "user data in Postgres — exactly the license, privacy, and platform Terms-of-Service rules "
           "our agent checks."),
    ("04", "One command. The agent scans the codebase with deterministic analyzers, and uses Gemini "
           "as a judge for the gray areas. On VidSeeds it found two real violations: personal data "
           "logged in seventy-three places across thirty-one files, and fourteen Apache-licensed "
           "dependencies with no NOTICE attribution. The U.S.A., Colorado, E.U., and YouTube rules "
           "were judged by Gemini, and flagged only when uncertain."),
    ("05", "For the deterministic issues, it fixes them in place. Here it generates the missing "
           "NOTICE file with every Apache dependency, and the re-scan confirms it's resolved. The "
           "personal-data-in-logs finding stays flagged, with the exact file and line, for a human "
           "to redact."),
    ("06", "Under the hood, it compiles source documents — Terms, laws, licenses, contracts — into "
           "versioned Policy Packs, and verifies that every clause actually exists in the source. It "
           "scans your repo into a fact model, judges it, and reports with citations. And it watches "
           "two kinds of drift: your code changing, and the upstream documents changing."),
    ("07", "It's open source, Apache two-point-oh. Pip-install and scan in about a minute — locally, "
           "no cloud required. And because it's single-tenant, it deploys into your own Google Cloud "
           "project, so your confidential documents never leave it. That's the Terms-of-Service and "
           "Compliance Agent."),
]


def synth(key: str, scene_id: str, text: str):
    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        "?output_format=mp3_44100_128"
    )
    body = json.dumps({
        "text": text,
        "model_id": MODEL,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.85,
            "style": 0.30,
            "use_speaker_boost": True,
        },
    }).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    path = OUT / f"scene_{scene_id}.mp3"
    path.write_bytes(data)
    print(f"scene {scene_id}: {len(data)} bytes -> {path.name}")


def main():
    key = load_key()
    for sid, text in SCENES:
        try:
            synth(key, sid, text)
        except urllib.error.HTTPError as e:
            print(f"scene {sid} FAILED: HTTP {e.code} {e.read().decode()[:200]}", file=sys.stderr)
            raise
    print("done")


if __name__ == "__main__":
    main()
