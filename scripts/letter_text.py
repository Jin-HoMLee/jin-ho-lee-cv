"""Deterministic cover-letter text serializer.

Emits two flavors from the same pre-resolved inputs:
  - "full": sender + date + recipient header + subject + salutation + body + closing
  - "body": salutation -> signature only (for EasyApply-style boxes)

PII note: the "full" sender block uses only the PUBLIC identity (name, email,
city/country). The private street/postal address is rendered only in the PDF,
which merges content.private/ at compile time and is gitignored.
"""

from __future__ import annotations

_FLAVORS = ("full", "body")


def _spans_text(spans: list[dict]) -> str:
    """Flatten {text, bold} spans to plain text (bold markup is dropped)."""
    return "".join(s["text"] for s in spans)


def _block_text(block: dict) -> str:
    """Render one body block to ATS-safe plain text: paragraph or `• ` bullet list."""
    if block["type"] == "bullet_list":
        return "\n".join("• " + _spans_text(item) for item in block["items"])
    return _spans_text(block["spans"])


def render(letter: dict, sender: dict, flavor: str) -> str:
    """Serialize a cover letter to plain text. `flavor` in {'full', 'body'}."""
    if flavor not in _FLAVORS:
        raise ValueError(f"unknown flavor {flavor!r}; expected one of {_FLAVORS}")

    body = "\n\n".join(_block_text(b) for b in letter["body_blocks"])
    parts: list[str] = []

    if flavor == "full":
        parts.append(sender["name"])
        if sender.get("location_line"):
            parts.append(sender["location_line"])
        parts.append(sender["email"])
        parts.append("")
        parts.append(letter["date_display"])

        recipient = letter.get("recipient")
        if recipient:
            rec_lines: list[str] = []
            if recipient.get("name"):
                rec_lines.append(recipient["name"])
            if recipient.get("company"):
                rec_lines.append(recipient["company"])
            address = recipient.get("address") or {}
            if address.get("street"):
                rec_lines.append(address["street"])
            pc_city = " ".join(
                x for x in (address.get("postal_code"), address.get("city")) if x
            ).strip()
            if pc_city:
                rec_lines.append(pc_city)
            if rec_lines:
                parts.append("")
                parts.extend(rec_lines)

        parts.append("")
        parts.append(letter["subject"])
        parts.append("")

    parts.append(letter["salutation"])
    parts.append("")
    if body:
        parts.append(body)
        parts.append("")
    parts.append(letter["closing"])
    parts.append(letter["signer_name"])
    return "\n".join(parts) + "\n"
