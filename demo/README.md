# Demo video

**▶ Watch:** https://youtu.be/OKi-HwaRFvo

A ~2:21 narrated walkthrough of the ToS/Compliance Agent, using a real production app
(VidSeeds) as the subject being scanned.

- **`tos-compliance-agent-demo-narrated.mp4`** — the narrated demo (ElevenLabs voiceover).
- **`tos-compliance-agent-demo.mp4`** — the silent slideshow (same visuals, no audio).
- **`shots/`** — the rendered 1080p slides.

## Regenerate

```bash
pip install pillow            # slides
python demo/render_slides.py  # -> demo/shots/*.png

# voiceover (needs an ElevenLabs API key in $ELEVENLABS_API_KEY or the path in the script)
python demo/make_voiceover.py # -> demo/audio/scene_*.mp3   (voice: "Eric", eleven_multilingual_v2)

# assemble: slides timed to each narration clip, then mux (see the build steps in git history)
```

The scan/fix scenes show the **real** output from running the agent against VidSeeds
(2 violations: PII-in-logs across 31 files; 14 Apache deps missing a NOTICE — auto-fixed).

## Narration script

1. **Title** — "The ToS/Compliance Agent is an open-source AI agent, built on Google Cloud, that keeps your project continuously compliant — it catches compliance drift, auto-fixes what it safely can, and flags the rest, every finding cited to the exact source clause."
2. **Problem** — "Software silently drifts out of compliance. A new dependency adds a license conflict. A PII field starts landing in your logs. A third-party API changes its Terms. A new privacy law starts to apply. Today you find out in an audit — or an incident."
3. **Real subject: VidSeeds** — "To prove it, we pointed it at VidSeeds — a real production video-SEO app. It publishes to YouTube, TikTok, Meta, LinkedIn and X, takes Stripe payments, and stores user data in Postgres — exactly the license, privacy, and platform-ToS rules our agent checks."
4. **Scan** — "One command. It scans with deterministic analyzers and uses Gemini as a judge for the gray areas. On VidSeeds it found two real violations: personal data logged in 73 places across 31 files, and 14 Apache-licensed dependencies with no NOTICE attribution. The USA, Colorado, EU and YouTube-ToS rules were judged by Gemini — flagged only when uncertain."
5. **Auto-fix** — "For the deterministic issues it fixes in place — generating the missing NOTICE with every Apache dependency, and the re-scan confirms it's resolved. The PII-in-logs finding stays flagged, with exact file and line, for a human to redact."
6. **How it works** — "It compiles source documents — Terms, laws, licenses, contracts — into versioned Policy Packs, and verifies every clause exists in the source. It scans your repo into a fact model, judges it, and reports with citations — watching two kinds of drift: your code changing, and the upstream documents changing."
7. **Call to action** — "It's open source, Apache-2.0 — pip-install and scan in about a minute, locally, no cloud required. And it's single-tenant: it deploys into your own Google Cloud project, so your confidential documents never leave it. That's the ToS/Compliance Agent."
