from dataclasses import dataclass


@dataclass(slots=True)
class DigestEntry:
    title: str
    tags: list[str]
    ai_engineering_fit: int
    url: str
    summary: str


@dataclass(slots=True)
class DigestSection:
    title: str
    entries: list[DigestEntry]


def render_digest_message(date_label: str, sections: list[DigestSection], experiments: list[str]) -> str:
    lines = [f"[AI Trend Digest | {date_label}]", ""]
    for section in sections:
        lines.append(section.title)
        for index, entry in enumerate(section.entries, start=1):
            lines.extend(
                [
                    f"{index}. {entry.title}",
                    entry.summary,
                    f"Link: {entry.url}",
                    "",
                ]
            )
    lines.append("Try This Today")
    for experiment in experiments:
        lines.append(f"- {experiment}")
    return "\n".join(lines).strip()
