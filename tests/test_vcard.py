BASE = "/api/v1/contacts"

PHOTO = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _create(client, payload, **overrides):
    body = {**payload, **overrides}
    response = client.post(BASE, json=body)
    assert response.status_code == 201
    return response.json()["id"]


def test_vcard_export_carries_the_whole_contact(client, payload):
    contact_id = _create(client, payload, photo=PHOTO)

    response = client.get(f"{BASE}/{contact_id}/vcard")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/vcard")
    assert 'filename="ada-lovelace.vcf"' in response.headers["content-disposition"]

    card = response.text
    assert card.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n")
    assert card.endswith("END:VCARD\r\n")
    assert "N:Lovelace;Ada;;;" in card
    assert "FN:Ada Lovelace" in card
    assert "EMAIL;TYPE=INTERNET:ada@example.com" in card
    assert "TEL;TYPE=VOICE:+1-415-555-0101" in card
    assert "ORG:Analytical Engines" in card
    assert "TITLE:Mathematician" in card
    assert "ADR;TYPE=HOME:;;1 Market St\\, Suite 400;San Francisco;CA;94105;USA" in card
    assert "PHOTO;ENCODING=b;TYPE=PNG:" in card


def test_vcard_escapes_separators_and_newlines(client, payload):
    contact_id = _create(
        client,
        payload,
        company="Sems; Colons, and\nNewlines",
        notes="line one\nline two",
    )

    card = client.get(f"{BASE}/{contact_id}/vcard").text
    assert "ORG:Sems\\; Colons\\, and\\nNewlines" in card
    assert "NOTE:line one\\nline two" in card


def test_vcard_omits_unset_fields(client, payload):
    contact_id = _create(
        client,
        {"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
    )

    card = client.get(f"{BASE}/{contact_id}/vcard").text
    for absent in ("TEL", "ORG:", "TITLE:", "ADR", "NOTE:", "PHOTO"):
        assert absent not in card, absent


def test_vcard_folds_long_lines(client, payload):
    contact_id = _create(client, payload, photo=PHOTO, notes="x" * 300)

    card = client.get(f"{BASE}/{contact_id}/vcard").text
    for line in card.split("\r\n"):
        assert len(line.encode("utf-8")) <= 76, line  # 75 + leading fold space
    assert "\r\n x" in card  # the NOTE actually folded


def test_vcard_missing_contact_returns_404(client):
    assert client.get(f"{BASE}/9999/vcard").status_code == 404
