import re
from pathlib import Path

from fastapi.testclient import TestClient

from labor_rights_rag.main import create_app

WEB = Path(__file__).parent.parent / "src" / "labor_rights_rag" / "web"


def test_home_page_is_hebrew_right_to_left_with_the_disclaimer() -> None:
    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<html lang="he" dir="rtl">' in response.text
    assert "אינו ייעוץ משפטי" in response.text
    assert "אל תכתבו פרטים אישיים" in response.text  # the question goes to an outside service


def test_home_page_has_a_policy_that_forbids_inline_scripts_and_other_origins() -> None:
    policy = TestClient(create_app()).get("/").headers["content-security-policy"]

    assert "default-src 'self'" in policy
    assert "unsafe-inline" not in policy
    assert "unsafe-eval" not in policy
    assert "frame-ancestors 'none'" in policy


def test_the_page_has_no_inline_script_or_style() -> None:
    page = (WEB / "index.html").read_text(encoding="utf-8")

    # The policy would block them: every script and style is a file of its own.
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", page)
    assert "<style" not in page
    assert not re.search(r"\son\w+=", page)  # no onclick= and the like


def test_the_script_and_the_style_are_served() -> None:
    client = TestClient(create_app())

    script = client.get("/static/app.js")
    style = client.get("/static/style.css")

    assert script.status_code == 200 and "javascript" in script.headers["content-type"]
    assert style.status_code == 200 and "text/css" in style.headers["content-type"]


def test_the_script_never_puts_server_text_on_the_page_as_html() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    # The quotes are law text from a wiki anyone can edit: only textContent is safe.
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert forbidden not in script, forbidden


def test_the_script_makes_links_only_for_https_addresses() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'startsWith("https://")' in script


def test_the_script_talks_to_the_ask_and_laws_endpoints() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'fetch("/ask"' in script
    assert 'fetch("/laws"' in script


def test_a_question_in_the_address_only_fills_the_box_and_asks() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'get("q")' in script
    assert "input.value = prefilled" in script


def test_a_text_newer_than_the_registry_is_not_shown_as_a_danger() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    # Only a text that may be older than the registry's is red; "ahead" is yellow.
    assert 'ahead: ["הנוסח חדש יותר מרישום הכנסת", "note"]' in script
    assert 'behind: ["ייתכן שהנוסח ישן", "attention"]' in script


def test_the_answer_and_the_refusal_have_a_heading() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'text: "התשובה"' in script
    assert 'text: "לא נמצאה תשובה"' in script


def test_enter_sends_and_shift_enter_makes_a_new_line_but_not_while_composing() -> None:
    script = (WEB / "app.js").read_text(encoding="utf-8")

    assert 'event.key === "Enter"' in script
    assert "!event.shiftKey" in script  # Shift+Enter keeps the browser's own new line
    assert "!event.isComposing" in script  # Enter confirms a word that is being composed
    assert "form.requestSubmit()" in script  # the same path as the button, with its checks
    assert "submit.disabled" in script  # no second question while one is being answered


def test_the_browser_must_check_the_script_with_the_server_every_time() -> None:
    client = TestClient(create_app())

    for path in ("/static/app.js", "/static/style.css", "/"):
        assert client.get(path).headers["cache-control"] == "no-cache", path


def test_the_page_names_each_file_with_a_version_taken_from_its_content() -> None:
    page = TestClient(create_app()).get("/").text

    assert re.search(r'/static/app\.js\?v=[0-9a-f]{10}"', page)
    assert re.search(r'/static/style\.css\?v=[0-9a-f]{10}"', page)


def test_a_changed_script_gets_a_new_address() -> None:
    from labor_rights_rag import main

    before = main.page_with_versioned_assets()
    script = WEB / "app.js"
    original = script.read_bytes()
    try:
        script.write_bytes(original + b"\n// changed\n")
        after = main.page_with_versioned_assets()
    finally:
        script.write_bytes(original)

    assert before != after
