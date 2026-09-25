"""Admin import endpoint tests (raw body + JSON envelope + auth + errors)."""
from sqlalchemy import select

from app.models import Race

FIXTURES_CSV = """date,race_no,venue,race_name,distance_m,race_class,track_condition,horse,jockey,trainer,barrier,weight_kg,odds
2026-05-12,3,Champ de Mars,Winter Plate,1400,Handicap,good,Belle Isle,J. Smith,T. Brown,1,55,3.5
2026-05-12,3,Champ de Mars,Winter Plate,1400,Handicap,good,Cafe Noir,A. Test,T. Practice,2,54.5,5
2026-05-12,4,Champ de Mars,Sprint Cup,1200,Maiden,soft,Quick Step,B. Sample,T. Fiction,3,56,2.8
"""

FIXTURES_HTML = """
<html><body><div class="race-card">Race 5 - 1800m - 12 May 2026
<table>
<tr><td>Saved Star</td><td>J. Smith</td><td>T. Brown</td><td>4</td><td>55</td><td>4.0</td></tr>
</table></div></body></html>
"""


def _admin_headers(client):
    resp = client.post("/api/auth/login",
                       json={"email": "admin@example.com", "password": "adminpass123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_import_endpoint_accepts_raw_csv_body(client, db):
    headers = {**_admin_headers(client), "Content-Type": "text/csv", "X-Filename": "card.csv"}
    resp = client.post("/api/admin/import?kind=auto", headers=headers,
                       content=FIXTURES_CSV.encode())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "fixtures-csv"
    assert body["races_created"] == 2
    assert body["imported_by"] == "admin"
    assert len(db.scalars(select(Race)).all()) == 2


def test_import_endpoint_accepts_json_envelope(client, db):
    payload = {"content": FIXTURES_HTML, "kind": "fixtures-html", "filename": "saved.html"}
    resp = client.post("/api/admin/import?kind=auto", headers=_admin_headers(client),
                       json=payload)
    assert resp.status_code == 200, resp.text
    assert resp.json()["races_created"] == 1


def test_import_endpoint_requires_admin(client):
    payload = {"content": FIXTURES_HTML, "kind": "fixtures-html"}
    assert client.post("/api/admin/import", json=payload).status_code == 401


def test_import_endpoint_rejects_empty_and_malformed(client):
    csv_headers = {**_admin_headers(client), "Content-Type": "text/csv"}
    assert client.post("/api/admin/import", headers=csv_headers, content=b"   ").status_code == 400

    json_headers = {**_admin_headers(client), "Content-Type": "application/json"}
    assert client.post("/api/admin/import", headers=json_headers,
                       content=b"{not json").status_code == 400
    assert client.post("/api/admin/import", headers=json_headers,
                       content=b'{"content": "  "}').status_code == 400
