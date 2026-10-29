import os
import subprocess
import sys

import pytest

import app as leftovers


@pytest.fixture
def client(tmp_path):
    leftovers.app.config.update(DB_PATH=str(tmp_path / "test.db"), TESTING=True)
    leftovers.init_db()
    c = leftovers.app.test_client()
    c.post("/login", data={"password": leftovers.app.config["APP_PASSWORD"]})
    return c


def make_labels(client, count=2, fmt="sheet"):
    res = client.post("/labels/print", data={"count": count, "format": fmt})
    assert res.status_code == 200
    assert res.data.startswith(b"%PDF")


def import_app(tmp_path, **env):
    env = {k: v for k, v in os.environ.items()
           if k not in ("LEFTOVERS_DEV", "SECRET_KEY", "APP_PASSWORD")} | env
    env["DB_PATH"] = str(tmp_path / "test.db")
    return subprocess.run([sys.executable, "-c", "import app"], env=env,
                          cwd=os.path.dirname(leftovers.__file__), capture_output=True, text=True)


def test_refuses_to_start_without_secrets(tmp_path):
    res = import_app(tmp_path)
    assert res.returncode != 0
    assert "SECRET_KEY environment variable must be set" in res.stderr

    res = import_app(tmp_path, SECRET_KEY="x")
    assert res.returncode != 0
    assert "APP_PASSWORD environment variable must be set" in res.stderr

    assert import_app(tmp_path, SECRET_KEY="x", APP_PASSWORD="y").returncode == 0


def test_requires_login(tmp_path):
    leftovers.app.config.update(DB_PATH=str(tmp_path / "test.db"))
    leftovers.init_db()
    c = leftovers.app.test_client()
    assert c.get("/api/items").status_code == 401
    assert c.get("/").status_code == 302


def test_full_lifecycle(client):
    make_labels(client)
    assert client.get("/api/labels/LO-0001").json == {"code": "LO-0001", "item": None}

    res = client.post("/api/items", json={"label_code": "lo-0001", "name": "Chili"})
    assert res.status_code == 201
    item = res.json
    assert item["stored_at"] and item["removed_at"] is None

    assert client.post("/api/items", json={"label_code": "LO-0001", "name": "Soup"}).status_code == 409
    assert [i["name"] for i in client.get("/api/items").json] == ["Chili"]

    res = client.post(f"/api/items/{item['id']}/remove", json={"outcome": "eaten"})
    assert res.json["outcome"] == "eaten"
    assert client.get("/api/items").json == []
    # Label is free again.
    assert client.post("/api/items", json={"label_code": "LO-0001", "name": "Soup"}).status_code == 201


def test_unknown_label(client):
    assert client.get("/api/labels/LO-9999").status_code == 404
    assert client.post("/api/items", json={"label_code": "LO-9999", "name": "X"}).status_code == 404


def test_label_numbering_continues_and_roll_format(client):
    make_labels(client, 2)
    make_labels(client, 1, fmt="roll")
    assert client.get("/api/labels/LO-0003").status_code == 200


def test_label_link_redirects(client):
    res = client.get("/l/lo-0005")
    assert res.status_code == 302
    assert res.location.endswith("/?label=LO-0005")
