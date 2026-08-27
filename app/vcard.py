"""Render a contact as a vCard 3.0 document (RFC 2426)."""

import re

from app.models import Address, Contact

# vCard type parameter per address label; "Other" has no standard type.
_ADR_TYPES = {"Home": "HOME", "Work": "WORK"}

_PHOTO_DATA_URL_RE = re.compile(r"^data:image/(?P<subtype>png|jpeg|gif|webp);base64,(?P<data>.+)$")

# Continuation lines start with a single space (RFC 2426 §2.6 line folding).
_MAX_LINE_OCTETS = 75


def _escape(value: str) -> str:
    """Escape text per RFC 2426 §2.4.2: backslash, separators, and newlines."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line: str) -> list[str]:
    """Split a content line into 75-octet chunks joined by CRLF + space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= _MAX_LINE_OCTETS:
        return [line]

    chunks: list[str] = []
    while encoded:
        cut = min(_MAX_LINE_OCTETS, len(encoded))
        # Never split inside a multi-byte UTF-8 sequence: back up while the
        # byte after the cut is a continuation byte (0b10xxxxxx).
        while cut < len(encoded) and cut > 1 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        chunks.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    return [chunks[0], *(" " + chunk for chunk in chunks[1:])]


def _adr_line(address: Address) -> str:
    adr_type = _ADR_TYPES.get(address.type)
    params = f";TYPE={adr_type}" if adr_type else ""
    components = (
        "",  # post office box
        "",  # extended address
        address.address or "",
        address.city or "",
        address.state or "",
        address.postal_code or "",
        address.country or "",
    )
    return f"ADR{params}:" + ";".join(_escape(part) for part in components)


def contact_to_vcard(contact: Contact) -> str:
    """Serialise a contact — names, contact points, typed addresses, photo."""
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{_escape(contact.last_name)};{_escape(contact.first_name)};;;",
        f"FN:{_escape(contact.full_name)}",
        f"EMAIL;TYPE=INTERNET:{_escape(contact.email)}",
    ]

    if contact.phone:
        lines.append(f"TEL;TYPE=VOICE:{_escape(contact.phone)}")
    if contact.company:
        lines.append(f"ORG:{_escape(contact.company)}")
    if contact.job_title:
        lines.append(f"TITLE:{_escape(contact.job_title)}")

    lines.extend(_adr_line(address) for address in contact.addresses)

    if contact.notes:
        lines.append(f"NOTE:{_escape(contact.notes)}")

    if contact.photo:
        match = _PHOTO_DATA_URL_RE.match(contact.photo)
        if match:  # photos are validated on write; skip quietly if not
            subtype = match.group("subtype").upper()
            lines.append(f"PHOTO;ENCODING=b;TYPE={subtype}:{match.group('data')}")

    lines.append(f"REV:{contact.updated_at.strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append("END:VCARD")

    folded = [chunk for line in lines for chunk in _fold(line)]
    return "\r\n".join(folded) + "\r\n"
