def _register(client, email="user@example.com", password="password123"):
    resp = client.post("/api/auth/register",
                       json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_register_login_me(client):
    token = _register(client)
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "user@example.com"

    login = client.post("/api/auth/login",
                        json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    bad = client.post("/api/auth/login",
                      json={"email": "user@example.com", "password": "wrong-wrong"})
    assert bad.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_admin_can_list_flags(client):
    token = _register(client, email="boss@example.com")
    # first registered user isn't admin by default; use bootstrap admin instead
    login = client.post("/api/auth/login",
                        json={"email": "admin@example.com", "password": "adminpass123"})
    assert login.status_code == 200, login.text
    admin_token = login.json()["access_token"]
    resp = client.get("/api/admin/flags",
                      headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["flags"] == []
    # non-admin forbidden
    forbidden = client.get("/api/admin/flags",
                           headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403
