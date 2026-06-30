from aitrendigest.digest import DigestEntry, DigestSection, render_digest_message


def test_render_digest_message_formats_sections_without_scores():
    sections = [
        DigestSection(
            title="AI 엔지니어링 핵심 5",
            entries=[
                DigestEntry(
                    title="Agent evaluation harness",
                    tags=["agent", "eval"],
                    ai_engineering_fit=91,
                    url="https://example.com/post",
                )
            ],
        )
    ]

    message = render_digest_message("2026-06-26", sections, ["Try the demo repo."])

    assert "[AI Trend Digest | 2026-06-26]" in message
    assert "AI 엔지니어링 핵심 5" in message
    assert "AI 엔지니어링 적합도" not in message
    assert "Link: https://example.com/post" in message
    assert "Try This Today" in message
