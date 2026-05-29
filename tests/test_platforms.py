from compliance_agent.scanners.platforms import detect_platform_apis


def test_detects_youtube_api_host(tmp_path):
    (tmp_path / "yt.ts").write_text(
        "const url = 'https://youtube.googleapis.com/youtube/v3/videos';\n"
    )
    assert detect_platform_apis(str(tmp_path)) == ["youtube"]


def test_detects_multiple_platforms(tmp_path):
    (tmp_path / "a.ts").write_text("fetch('https://graph.facebook.com/v19.0/me')\n")
    (tmp_path / "b.py").write_text("URL='https://open-api.tiktok.com/v2/'\n")
    (tmp_path / "c.js").write_text("const li='https://api.linkedin.com/v2/me'\n")
    assert detect_platform_apis(str(tmp_path)) == ["linkedin", "meta", "tiktok"]


def test_ignores_generic_youtube_dot_com(tmp_path):
    # A plain youtube.com watch link is NOT an API integration signal.
    (tmp_path / "a.ts").write_text("const link = 'https://www.youtube.com/watch?v=abc'\n")
    assert detect_platform_apis(str(tmp_path)) == []


def test_skips_node_modules(tmp_path):
    nm = tmp_path / "node_modules" / "dep"
    nm.mkdir(parents=True)
    (nm / "i.js").write_text("https://api.twitter.com/2/tweets\n")
    assert detect_platform_apis(str(tmp_path)) == []


def test_none_detected(tmp_path):
    (tmp_path / "a.py").write_text("print('hello')\n")
    assert detect_platform_apis(str(tmp_path)) == []


def test_detects_host_in_dotenv_file(tmp_path):
    # .env / .env.local have no ".env" suffix; they must still be scanned.
    (tmp_path / ".env.local").write_text("YT_API=https://youtube.googleapis.com/youtube/v3\n")
    assert detect_platform_apis(str(tmp_path)) == ["youtube"]
