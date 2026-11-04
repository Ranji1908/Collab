"""Tests für das Open-WebUI-Tool gegen eine simulierte n8n-API (kein echtes n8n nötig)."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "openwebui" / "tools"))
from n8n_workflows import SETUP_HINT, Tools  # noqa: E402


class FakeN8n:
    """Minimaler In-Memory-Ersatz für die n8n Public API, getrennt nach API-Key."""

    def __init__(self):
        self.keys = {"key-anna": "anna", "key-ben": "ben", "key-admin": "admin"}
        self.workflows = {}  # id -> (owner, wf)
        self.credentials = {}  # id -> (owner, cred)
        self.tags = []
        self.calls = []
        self._id = 0

    def _next(self):
        self._id += 1
        return str(self._id)

    def handler(self, req: httpx.Request) -> httpx.Response:
        user = self.keys.get(req.headers.get("X-N8N-API-KEY"))
        if not user:
            return httpx.Response(401, json={"message": "unauthorized"})
        path = req.url.path.removeprefix("/api/v1")
        body = json.loads(req.content) if req.content else None
        self.calls.append((req.method, path, user, body))

        if path == "/users":
            return httpx.Response(200, json={"data": []}) if user == "admin" else httpx.Response(403, json={"message": "forbidden"})
        if path == "/workflows" and req.method == "GET":
            data = [w for o, w in self.workflows.values() if o == user or user == "admin"]
            return httpx.Response(200, json={"data": data, "nextCursor": None})
        if path == "/workflows" and req.method == "POST":
            assert set(body) <= {"name", "nodes", "connections", "settings"}
            wid = self._next()
            wf = {**body, "id": wid, "active": False, "tags": []}
            self.workflows[wid] = (user, wf)
            return httpx.Response(200, json=wf)
        if path.startswith("/workflows/"):
            parts = path.split("/")
            wid = parts[2]
            if wid not in self.workflows or self.workflows[wid][0] != user:
                return httpx.Response(404, json={"message": "Not Found"})
            wf = self.workflows[wid][1]
            if len(parts) == 3 and req.method == "GET":
                return httpx.Response(200, json=wf)
            if len(parts) == 3 and req.method == "PUT":
                wf.update(body)
                return httpx.Response(200, json=wf)
            if parts[3] == "tags":
                wf["tags"] = body
                return httpx.Response(200, json=body)
            if parts[3] == "activate":
                wf["active"] = True
                return httpx.Response(200, json=wf)
        if path == "/tags" and req.method == "GET":
            return httpx.Response(200, json={"data": self.tags, "nextCursor": None})
        if path == "/tags" and req.method == "POST":
            t = {"id": self._next(), "name": body["name"]}
            self.tags.append(t)
            return httpx.Response(201, json=t)
        if path.startswith("/credentials/schema/"):
            return httpx.Response(200, json={
                "properties": {"host": {"type": "string"}, "port": {"type": "number"},
                               "user": {"type": "string"}, "password": {"type": "string"}},
                "required": ["host", "user", "password"],
            })
        if path == "/credentials" and req.method == "POST":
            cid = self._next()
            cred = {"id": cid, "name": body["name"], "type": body["type"], "_data": body["data"]}
            self.credentials[cid] = (user, cred)
            return httpx.Response(200, json={k: v for k, v in cred.items() if k != "_data"})
        if path == "/credentials" and req.method == "GET":
            data = [{k: v for k, v in c.items() if k != "_data"} for o, c in self.credentials.values() if o == user]
            return httpx.Response(200, json={"data": data, "nextCursor": None})
        return httpx.Response(404, json={"message": f"no route {req.method} {path}"})


@pytest.fixture
def env():
    fake = FakeN8n()
    tool = Tools()
    tool._transport = httpx.MockTransport(fake.handler)
    tool.valves.n8n_public_url = "https://n8n.test"
    return tool, fake


def user(key):
    return {"id": key, "valves": Tools.UserValves(n8n_api_key=key)}


NODES = [
    {"name": "Jeden Montag", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2,
     "parameters": {"rule": {"interval": [{"field": "weeks"}]}}},
    {"name": "Mail senden", "type": "n8n-nodes-base.emailSend", "typeVersion": 2.1,
     "parameters": {"toEmail": "a@b.de", "subject": "Hi"}},
]
CONNS = {"Jeden Montag": {"main": [[{"node": "Mail senden", "type": "main", "index": 0}]]}}


async def test_no_key_gives_setup_hint(env):
    tool, _ = env
    assert await tool.list_my_workflows(__user__={"id": "x", "valves": Tools.UserValves()}) == SETUP_HINT


async def test_admin_key_rejected(env):
    tool, _ = env
    assert "Owner/Admin" in await tool.check_connection(__user__=user("key-admin"))


async def test_create_and_isolation(env):
    tool, fake = env
    res = json.loads(await tool.create_workflow("Test", json.dumps(NODES), json.dumps(CONNS), __user__=user("key-anna")))
    assert res["result"] == "created" and res["url"] == f"https://n8n.test/workflow/{res['id']}"
    assert res["nodes_without_credentials"] == ["Mail senden (n8n-nodes-base.emailSend)"]
    wf = fake.workflows[res["id"]][1]
    assert all("id" in n and "position" in n for n in wf["nodes"])
    assert wf["tags"] and wf["active"] is False

    assert "Test" in await tool.list_my_workflows(__user__=user("key-anna"))
    assert await tool.list_my_workflows(__user__=user("key-ben")) == "Keine Workflows gefunden."
    assert "404" in await tool.get_workflow(res["id"], __user__=user("key-ben"))


async def test_blocked_node_and_bad_connection(env):
    tool, fake = env
    bad = NODES + [{"name": "Shell", "type": "n8n-nodes-base.executeCommand", "parameters": {}}]
    assert "gesperrt" in await tool.create_workflow("x", json.dumps(bad), "{}", __user__=user("key-anna"))
    conns = {"Jeden Montag": {"main": [[{"node": "Gibtsnicht", "type": "main", "index": 0}]]}}
    assert "unbekannten Ziel-Node" in await tool.create_workflow("x", json.dumps(NODES), json.dumps(conns), __user__=user("key-anna"))
    assert not fake.workflows


async def test_activation_requires_confirmation(env):
    tool, fake = env
    res = json.loads(await tool.create_workflow("T", json.dumps(NODES), json.dumps(CONNS), __user__=user("key-anna")))
    assert "ausdrücklich" in await tool.set_workflow_active(res["id"], True, __user__=user("key-anna"))
    assert fake.workflows[res["id"]][1]["active"] is False
    await tool.set_workflow_active(res["id"], True, user_confirmed=True, __user__=user("key-anna"))
    assert fake.workflows[res["id"]][1]["active"] is True


async def test_credential_secrets_via_dialog_and_attach(env):
    tool, fake = env
    # Geheimnis im Chat → abgelehnt
    assert "⛔" in await tool.create_credential("smtp", "SMTP", json.dumps({"password": "x"}), __user__=user("key-anna"))

    asked = []

    async def event_call(ev):
        asked.append(ev["data"]["title"])
        return "geheim123"

    res = json.loads(await tool.create_credential(
        "smtp", "SMTP Anna", json.dumps({"host": "mail.test", "user": "anna", "port": 587}),
        __user__=user("key-anna"), __event_call__=event_call,
    ))
    assert asked == ["SMTP Anna: password"]
    assert fake.credentials[res["id"]][1]["_data"]["password"] == "geheim123"
    assert "geheim123" not in json.dumps(res)

    wf = json.loads(await tool.create_workflow("T", json.dumps(NODES), json.dumps(CONNS), __user__=user("key-anna")))
    out = await tool.attach_credential(wf["id"], "Mail senden", res["id"], __user__=user("key-anna"))
    assert out.startswith("✅")
    node = next(n for n in fake.workflows[wf["id"]][1]["nodes"] if n["name"] == "Mail senden")
    assert node["credentials"] == {"smtp": {"id": res["id"], "name": "SMTP Anna"}}
    # Ben sieht Annas Credential nicht
    assert "nicht gefunden" in await tool.attach_credential(wf["id"], "Mail senden", res["id"], __user__=user("key-ben"))
