"""
title: n8n Workflows
author: Collab
description: Legt n8n-Workflows und Credentials im Konto des jeweiligen Nutzers an. Jeder Nutzer hinterlegt seinen eigenen n8n-API-Key (UserValves) und sieht nur seine eigenen Workflows.
version: 0.2.0
license: MIT
requirements: httpx
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Awaitable, Callable, Optional

import httpx
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

SETUP_HINT = """⚠️ Es ist noch kein n8n-API-Key hinterlegt.

So richtest du ihn einmalig ein:
1. In n8n einloggen → unten links auf dein Profil → **Settings** → **n8n API** → **Create an API key**.
   - Label z. B. „Open WebUI“, Ablaufdatum nach Firmenrichtlinie.
   - Scopes (falls auswählbar): alle `workflow:*`, `credential:create`, `credential:list`,
     `credential:read`, `execution:read`, `execution:list`, `project:list`, `tag:*`.
2. Key kopieren (er wird nur einmal angezeigt).
3. Hier im Chat: unter dem Eingabefeld auf das **Werkzeug-Symbol** → bei **n8n Workflows** auf das
   **Zahnrad** → Key in „n8n_api_key“ einfügen → **Speichern**.
4. Danach einfach nochmal fragen."""

# Erlaubte Top-Level-Felder für settings beim Anlegen/Ändern (n8n Public API ist strikt)
ALLOWED_SETTINGS = {
    "executionOrder",
    "saveExecutionProgress",
    "saveManualExecutions",
    "saveDataErrorExecution",
    "saveDataSuccessExecution",
    "executionTimeout",
    "errorWorkflow",
    "timezone",
    "callerPolicy",
    "callerIds",
}

SECRET_HINTS = ("password", "secret", "token", "apikey", "api_key", "key", "privatekey")


class N8nError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class NoKeyError(Exception):
    pass


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class Tools:
    class Valves(BaseModel):
        """Nur für Admins sichtbar."""

        n8n_base_url: str = Field(
            default="http://n8n:5678",
            description="Interne URL, unter der Open WebUI n8n erreicht (ohne /api/v1).",
        )
        n8n_public_url: str = Field(
            default="https://n8n.example.com",
            description="Öffentliche n8n-URL für Links an die Nutzer.",
        )
        allowed_node_prefixes: str = Field(
            default="n8n-nodes-base.,@n8n/n8n-nodes-langchain.",
            description="Kommagetrennte Präfixe erlaubter Node-Typen.",
        )
        blocked_nodes: str = Field(
            default="n8n-nodes-base.executeCommand,n8n-nodes-base.ssh,n8n-nodes-base.readWriteFile,n8n-nodes-base.localFileTrigger",
            description="Kommagetrennte Liste explizit gesperrter Node-Typen.",
        )
        default_tag: str = Field(
            default="openwebui",
            description="Tag, das jeder über Open WebUI angelegte Workflow bekommt (leer = keins).",
        )
        reject_admin_keys: bool = Field(
            default=True,
            description="Keys von n8n-Owner/Admin ablehnen (die sehen ALLE Workflows).",
        )
        allow_activation: bool = Field(
            default=True,
            description="Darf das Modell Workflows aktivieren/publizieren (nach Bestätigung)?",
        )
        timeout_seconds: int = Field(default=30)

    class UserValves(BaseModel):
        """Pro Nutzer – im Chat über Werkzeug-Symbol → Zahnrad einstellbar."""

        n8n_api_key: str = Field(
            default="",
            description="Dein persönlicher n8n-API-Key (n8n → Settings → n8n API).",
        )
        default_project_id: str = Field(
            default="",
            description="Optional: n8n-Projekt-ID, in das neue Workflows verschoben werden (leer = persönliches Projekt).",
        )

    def __init__(self):
        self.valves = self.Valves()
        # Für Tests kann hier ein httpx-Transport injiziert werden.
        self._transport: Optional[httpx.AsyncBaseTransport] = None

    # ------------------------------------------------------------------ intern

    @staticmethod
    def _user_valve(__user__: Optional[dict], name: str) -> str:
        if not __user__:
            return ""
        uv = __user__.get("valves")
        if uv is None:
            return ""
        if isinstance(uv, dict):
            return str(uv.get(name, "") or "").strip()
        return str(getattr(uv, name, "") or "").strip()

    def _client(self, __user__: Optional[dict]) -> httpx.AsyncClient:
        key = self._user_valve(__user__, "n8n_api_key")
        if not key:
            raise NoKeyError()
        return httpx.AsyncClient(
            base_url=self.valves.n8n_base_url.rstrip("/") + "/api/v1",
            headers={"X-N8N-API-KEY": key, "Accept": "application/json"},
            timeout=self.valves.timeout_seconds,
            transport=self._transport,
        )

    async def _req(
        self, client: httpx.AsyncClient, method: str, path: str, **kw
    ) -> Any:
        r = await client.request(method, path, **kw)
        if r.status_code >= 400:
            try:
                msg = r.json().get("message") or r.text
            except Exception:
                msg = r.text
            raise N8nError(r.status_code, str(msg)[:1500])
        if not r.content:
            return None
        try:
            return r.json()
        except Exception:
            return r.text

    async def _paginate(
        self, client: httpx.AsyncClient, path: str, params: dict, max_items: int = 500
    ) -> list:
        items: list = []
        params = dict(params)
        params.setdefault("limit", 100)
        while True:
            data = await self._req(client, "GET", path, params=params)
            items.extend(data.get("data", []))
            cursor = data.get("nextCursor")
            if not cursor or len(items) >= max_items:
                return items[:max_items]
            params["cursor"] = cursor

    def _wf_url(self, wf_id: str) -> str:
        return f"{self.valves.n8n_public_url.rstrip('/')}/workflow/{wf_id}"

    def _cred_url(self, cred_id: str) -> str:
        return f"{self.valves.n8n_public_url.rstrip('/')}/home/credentials/{cred_id}"

    @staticmethod
    def _err(e: Exception) -> str:
        if isinstance(e, NoKeyError):
            return SETUP_HINT
        if isinstance(e, N8nError):
            if e.status == 401:
                return "❌ n8n lehnt den API-Key ab (401). Bitte Key in den Tool-Einstellungen prüfen oder neu erzeugen.\n\n" + SETUP_HINT
            if e.status == 403:
                return f"❌ Keine Berechtigung (403): {e.message}\nVermutlich fehlt dem API-Key ein Scope."
            return f"❌ Fehler von n8n ({e.status}): {e.message}"
        if isinstance(e, httpx.HTTPError):
            return f"❌ n8n nicht erreichbar: {e}. Bitte Admin informieren (Valve n8n_base_url)."
        if isinstance(e, (ValueError, json.JSONDecodeError)):
            return f"❌ Ungültige Eingabe: {e}"
        return f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}"

    @staticmethod
    async def _status(emitter, text: str, done: bool = False):
        if emitter:
            await emitter({"type": "status", "data": {"description": text, "done": done}})

    async def _is_admin_key(self, client: httpx.AsyncClient) -> bool:
        """Owner/Admin dürfen /users listen, Member nicht."""
        try:
            await self._req(client, "GET", "/users", params={"limit": 1})
            return True
        except N8nError as e:
            if e.status in (401, 403):
                return False
            # 404 o. ä. → unklar, nicht blockieren
            return False

    async def _guard(self, client: httpx.AsyncClient) -> Optional[str]:
        if self.valves.reject_admin_keys and await self._is_admin_key(client):
            return (
                "⛔ Dieser API-Key gehört zu einem n8n-Owner/Admin und hätte Zugriff auf ALLE Workflows. "
                "Bitte einen Key eines normalen Nutzerkontos (Rolle Member) verwenden."
            )
        return None

    # ---------------------------------------------------------- Validierung

    def _validate_nodes(self, nodes: Any, connections: Any) -> tuple[list, dict]:
        if not isinstance(nodes, list) or not nodes:
            raise ValueError("nodes muss ein nicht-leeres JSON-Array sein.")
        if not isinstance(connections, dict):
            raise ValueError("connections muss ein JSON-Objekt sein.")

        prefixes = [p.strip() for p in self.valves.allowed_node_prefixes.split(",") if p.strip()]
        blocked = {b.strip() for b in self.valves.blocked_nodes.split(",") if b.strip()}
        names: set[str] = set()

        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                raise ValueError(f"Node #{i} ist kein Objekt.")
            ntype = n.get("type")
            name = n.get("name")
            if not ntype or not name:
                raise ValueError(f"Node #{i} braucht 'type' und 'name'.")
            if name in names:
                raise ValueError(f"Node-Name doppelt: {name!r}")
            names.add(name)
            if ntype in blocked:
                raise ValueError(f"Node-Typ {ntype} ist vom Admin gesperrt.")
            if prefixes and not any(ntype.startswith(p) for p in prefixes):
                raise ValueError(f"Node-Typ {ntype} ist nicht erlaubt (erlaubte Präfixe: {', '.join(prefixes)}).")
            n.setdefault("id", str(uuid.uuid4()))
            n.setdefault("parameters", {})
            n.setdefault("typeVersion", 1)
            pos = n.get("position")
            if not (isinstance(pos, list) and len(pos) == 2):
                n["position"] = [250 + 220 * i, 300]
            # Credentials, die nur Platzhalter sind, entfernen – sonst lehnt n8n ab
            creds = n.get("credentials")
            if isinstance(creds, dict):
                clean = {k: v for k, v in creds.items() if isinstance(v, dict) and v.get("id")}
                if clean:
                    n["credentials"] = clean
                else:
                    n.pop("credentials", None)

        for src, outputs in connections.items():
            if src not in names:
                raise ValueError(f"connections verweist auf unbekannten Node {src!r}.")
            if not isinstance(outputs, dict):
                raise ValueError(f"connections[{src!r}] muss ein Objekt sein.")
            for _ctype, branches in outputs.items():
                for branch in branches or []:
                    for target in branch or []:
                        if target.get("node") not in names:
                            raise ValueError(
                                f"connections[{src!r}] verweist auf unbekannten Ziel-Node {target.get('node')!r}."
                            )
        return nodes, connections

    @staticmethod
    def _clean_settings(settings: Optional[dict]) -> dict:
        s = {k: v for k, v in (settings or {}).items() if k in ALLOWED_SETTINGS}
        s.setdefault("executionOrder", "v1")
        return s

    @staticmethod
    def _parse_json(value: Any, what: str) -> Any:
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"{what} ist kein gültiges JSON: {e}") from e

    @staticmethod
    def _missing_credentials(nodes: list) -> list[str]:
        """Nodes, die typischerweise Credentials brauchen, aber keine haben (Heuristik)."""
        no_cred = (
            "trigger", "manualTrigger", "scheduleTrigger", "set", "if", "switch", "merge", "code",
            "noOp", "wait", "splitInBatches", "filter", "aggregate", "sort", "limit", "webhook",
            "respondToWebhook", "dateTime", "itemLists", "splitOut", "removeDuplicates", "summarize",
            "html", "xml", "markdown", "crypto", "compareDatasets", "stickyNote", "executeWorkflow",
            "executeWorkflowTrigger", "errorTrigger", "formTrigger", "form", "chatTrigger", "httpRequest",
            "renameKeys", "editImage", "compression", "convertToFile", "extractFromFile", "rssFeedRead",
        )
        out = []
        for n in nodes:
            short = n["type"].split(".")[-1]
            if n.get("credentials"):
                continue
            if short in no_cred:
                continue
            if n["type"].startswith("@n8n/n8n-nodes-langchain.") and not short.startswith("lm"):
                continue
            out.append(f"{n['name']} ({n['type']})")
        return out

    # ================================================================ TOOLS

    async def check_connection(
        self, __user__: dict = None, __event_emitter__: Callable[[dict], Awaitable[None]] = None
    ) -> str:
        """
        Prüft, ob der n8n-API-Key des aktuellen Nutzers hinterlegt ist und funktioniert.
        Immer als Erstes aufrufen, bevor Workflows angelegt werden.
        """
        try:
            async with self._client(__user__) as c:
                await self._status(__event_emitter__, "Verbinde mit n8n …")
                await self._req(c, "GET", "/workflows", params={"limit": 1})
                if guard := await self._guard(c):
                    return guard
                await self._status(__event_emitter__, "Verbunden", True)
                return "✅ Verbindung zu n8n OK. Der Key gehört zu einem normalen Nutzerkonto."
        except Exception as e:
            return self._err(e)

    async def list_my_workflows(
        self, search: str = "", only_openwebui: bool = False, __user__: dict = None
    ) -> str:
        """
        Listet die n8n-Workflows, auf die der aktuelle Nutzer Zugriff hat.
        :param search: Optionaler Suchbegriff im Workflow-Namen.
        :param only_openwebui: Nur Workflows, die über Open WebUI angelegt wurden.
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                params: dict = {"excludePinnedData": "true"}
                if search:
                    params["name"] = search
                if only_openwebui and self.valves.default_tag:
                    params["tags"] = self.valves.default_tag
                wfs = await self._paginate(c, "/workflows", params)
        except Exception as e:
            return self._err(e)
        if search:
            wfs = [w for w in wfs if search.lower() in w.get("name", "").lower()]
        if not wfs:
            return "Keine Workflows gefunden."
        rows = [
            {
                "id": w["id"],
                "name": w.get("name"),
                "active": w.get("active"),
                "updatedAt": w.get("updatedAt"),
                "tags": [t.get("name") for t in w.get("tags", []) or []],
                "url": self._wf_url(w["id"]),
            }
            for w in wfs
        ]
        return json.dumps(rows, ensure_ascii=False, indent=1)

    async def get_workflow(self, workflow_id: str, __user__: dict = None) -> str:
        """
        Lädt einen Workflow vollständig (nodes, connections, settings), z. B. um ihn zu ändern.
        :param workflow_id: ID des Workflows.
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                wf = await self._req(c, "GET", f"/workflows/{workflow_id}", params={"excludePinnedData": "true"})
        except Exception as e:
            return self._err(e)
        slim = {k: wf.get(k) for k in ("id", "name", "active", "nodes", "connections", "settings")}
        slim["url"] = self._wf_url(wf["id"])
        return json.dumps(slim, ensure_ascii=False)

    async def create_workflow(
        self,
        name: str,
        nodes_json: str,
        connections_json: str,
        settings_json: str = "{}",
        project_id: str = "",
        __user__: dict = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
    ) -> str:
        """
        Legt einen neuen, INAKTIVEN n8n-Workflow im Konto des aktuellen Nutzers an.
        :param name: Sprechender Name des Workflows.
        :param nodes_json: JSON-Array der n8n-Nodes (jeweils name, type, typeVersion, position, parameters; credentials nur mit echter ID).
        :param connections_json: JSON-Objekt der Verbindungen im n8n-Format {"Quelle": {"main": [[{"node": "Ziel", "type": "main", "index": 0}]]}}.
        :param settings_json: Optionale Workflow-Settings als JSON-Objekt (z. B. timezone).
        :param project_id: Optional: Projekt-ID, in das der Workflow verschoben wird.
        """
        try:
            nodes = self._parse_json(nodes_json, "nodes_json")
            conns = self._parse_json(connections_json, "connections_json")
            settings = self._parse_json(settings_json or "{}", "settings_json")
            nodes, conns = self._validate_nodes(nodes, conns)
            body = {
                "name": name.strip() or "Neuer Workflow",
                "nodes": nodes,
                "connections": conns,
                "settings": self._clean_settings(settings),
            }
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                await self._status(__event_emitter__, "Lege Workflow in n8n an …")
                wf = await self._req(c, "POST", "/workflows", json=body)
                notes = []
                if self.valves.default_tag:
                    try:
                        await self._tag(c, wf["id"], self.valves.default_tag)
                    except N8nError as e:
                        notes.append(f"Tag konnte nicht gesetzt werden ({e.status}).")
                target_project = project_id or self._user_valve(__user__, "default_project_id")
                if target_project:
                    try:
                        await self._req(
                            c, "PUT", f"/workflows/{wf['id']}/transfer",
                            json={"destinationProjectId": target_project},
                        )
                        notes.append(f"In Projekt {target_project} verschoben.")
                    except N8nError as e:
                        notes.append(f"Verschieben ins Projekt fehlgeschlagen: {e.message}")
                await self._status(__event_emitter__, "Workflow angelegt", True)
        except Exception as e:
            return self._err(e)

        missing = self._missing_credentials(nodes)
        out = {
            "result": "created",
            "id": wf["id"],
            "name": wf.get("name"),
            "active": False,
            "url": self._wf_url(wf["id"]),
            "nodes_without_credentials": missing,
            "notes": notes,
        }
        return json.dumps(out, ensure_ascii=False)

    async def update_workflow(
        self,
        workflow_id: str,
        nodes_json: str = "",
        connections_json: str = "",
        name: str = "",
        settings_json: str = "",
        __user__: dict = None,
    ) -> str:
        """
        Ändert einen bestehenden Workflow. Nicht übergebene Teile bleiben unverändert.
        Vorher mit get_workflow den aktuellen Stand laden und vollständige nodes/connections übergeben.
        :param workflow_id: ID des Workflows.
        :param nodes_json: Vollständiges neues JSON-Array der Nodes (optional).
        :param connections_json: Vollständiges neues connections-Objekt (optional).
        :param name: Neuer Name (optional).
        :param settings_json: Neue Settings als JSON-Objekt (optional).
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                cur = await self._req(c, "GET", f"/workflows/{workflow_id}")
                nodes = self._parse_json(nodes_json, "nodes_json") if nodes_json else cur["nodes"]
                conns = self._parse_json(connections_json, "connections_json") if connections_json else cur["connections"]
                settings = self._parse_json(settings_json, "settings_json") if settings_json else cur.get("settings")
                nodes, conns = self._validate_nodes(nodes, conns)
                body = {
                    "name": name.strip() or cur["name"],
                    "nodes": nodes,
                    "connections": conns,
                    "settings": self._clean_settings(settings),
                }
                wf = await self._req(c, "PUT", f"/workflows/{workflow_id}", json=body)
        except Exception as e:
            return self._err(e)
        return json.dumps(
            {"result": "updated", "id": wf["id"], "name": wf.get("name"), "active": wf.get("active"),
             "url": self._wf_url(wf["id"]), "nodes_without_credentials": self._missing_credentials(nodes)},
            ensure_ascii=False,
        )

    async def set_workflow_active(
        self, workflow_id: str, active: bool, user_confirmed: bool = False, __user__: dict = None
    ) -> str:
        """
        Aktiviert (publiziert) oder deaktiviert einen Workflow.
        Nur aufrufen, nachdem der Nutzer im Chat ausdrücklich zugestimmt hat.
        :param workflow_id: ID des Workflows.
        :param active: true = aktivieren, false = deaktivieren.
        :param user_confirmed: Muss true sein – der Nutzer hat ausdrücklich bestätigt.
        """
        if active and not self.valves.allow_activation:
            return "Aktivieren über den Chat ist vom Admin deaktiviert. Bitte direkt in n8n aktivieren: " + self._wf_url(workflow_id)
        if active and not user_confirmed:
            return "Bitte zuerst den Nutzer ausdrücklich fragen, ob der Workflow aktiviert werden soll."
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                path = f"/workflows/{workflow_id}/{'activate' if active else 'deactivate'}"
                wf = await self._req(c, "POST", path)
        except N8nError as e:
            if active and e.status == 400:
                return (
                    f"❌ n8n konnte den Workflow nicht aktivieren: {e.message}\n"
                    "Häufige Ursachen: fehlende Credentials, kein Trigger-Node, ungültige Parameter. "
                    f"Bitte in n8n öffnen und rot markierte Nodes prüfen: {self._wf_url(workflow_id)}"
                )
            return self._err(e)
        except Exception as e:
            return self._err(e)
        return json.dumps({"id": workflow_id, "active": (wf or {}).get("active", active), "url": self._wf_url(workflow_id)})

    async def list_executions(
        self, workflow_id: str = "", only_errors: bool = False, limit: int = 10, __user__: dict = None
    ) -> str:
        """
        Zeigt die letzten Ausführungen (z. B. zur Fehlersuche).
        :param workflow_id: Optional nur für diesen Workflow.
        :param only_errors: Nur fehlgeschlagene Ausführungen.
        :param limit: Anzahl (max. 50).
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                params: dict = {"limit": max(1, min(int(limit), 50)), "includeData": "false"}
                if workflow_id:
                    params["workflowId"] = workflow_id
                if only_errors:
                    params["status"] = "error"
                data = await self._req(c, "GET", "/executions", params=params)
        except Exception as e:
            return self._err(e)
        rows = [
            {k: x.get(k) for k in ("id", "workflowId", "status", "mode", "startedAt", "stoppedAt")}
            for x in data.get("data", [])
        ]
        return json.dumps(rows, ensure_ascii=False, indent=1) if rows else "Keine Ausführungen gefunden."

    async def get_execution_error(self, execution_id: str, __user__: dict = None) -> str:
        """
        Liefert die Fehlermeldung einer fehlgeschlagenen Ausführung (ohne Nutzdaten).
        :param execution_id: ID der Ausführung.
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                ex = await self._req(c, "GET", f"/executions/{execution_id}", params={"includeData": "true"})
        except Exception as e:
            return self._err(e)
        rd = ((ex.get("data") or {}).get("resultData") or {})
        err = rd.get("error") or {}
        return json.dumps(
            {
                "status": ex.get("status"),
                "lastNode": rd.get("lastNodeExecuted"),
                "error": {k: err.get(k) for k in ("message", "description", "httpCode") if err.get(k)},
            },
            ensure_ascii=False,
        )

    # ------------------------------------------------------------ Credentials

    async def list_my_credentials(self, __user__: dict = None) -> str:
        """
        Listet die Credentials (Zugangsdaten), die der Nutzer in n8n hat – nur Name, Typ und ID, keine Geheimnisse.
        Nützlich, um vorhandene Credentials an neue Workflows zu hängen.
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                creds = await self._paginate(c, "/credentials", {})
        except Exception as e:
            return self._err(e)
        rows = [{"id": x["id"], "name": x.get("name"), "type": x.get("type")} for x in creds]
        return json.dumps(rows, ensure_ascii=False, indent=1) if rows else "Noch keine Credentials vorhanden."

    async def get_credential_requirements(self, credential_type: str, __user__: dict = None) -> str:
        """
        Liefert, welche Felder ein n8n-Credential-Typ braucht (z. B. 'microsoftOutlookOAuth2Api',
        'googleSheetsOAuth2Api', 'slackApi', 'smtp', 'httpHeaderAuth'), ob es OAuth ist,
        und welche Redirect-URL bei OAuth beim Anbieter eingetragen werden muss.
        :param credential_type: Interner n8n-Credential-Typname.
        """
        try:
            async with self._client(__user__) as c:
                schema = await self._req(c, "GET", f"/credentials/schema/{credential_type}")
        except Exception as e:
            if isinstance(e, N8nError) and e.status == 404:
                return f"Credential-Typ {credential_type!r} gibt es in dieser n8n-Version nicht. Bitte Typnamen prüfen."
            return self._err(e)
        props = schema.get("properties", {}) or {}
        required = schema.get("required", []) or []
        fields = [
            {
                "name": k,
                "type": v.get("type"),
                "required": k in required,
                "secret": self._is_secret(k),
                "options": v.get("enum"),
            }
            for k, v in props.items()
        ]
        is_oauth2 = "oauth2" in credential_type.lower()
        is_oauth1 = "oauth1" in credential_type.lower()
        base = self.valves.n8n_public_url.rstrip("/")
        return json.dumps(
            {
                "credential_type": credential_type,
                "auth": "oauth2" if is_oauth2 else "oauth1" if is_oauth1 else "static",
                "fields": fields,
                "oauth_redirect_url": (
                    f"{base}/rest/oauth2-credential/callback" if is_oauth2
                    else f"{base}/rest/oauth1-credential/callback" if is_oauth1 else None
                ),
                "after_create": (
                    "Nutzer muss das Credential in n8n öffnen und 'Connect my account' klicken."
                    if (is_oauth2 or is_oauth1) else "Sofort nutzbar."
                ),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _is_secret(field: str) -> bool:
        f = field.lower().replace("-", "").replace("_", "")
        return any(h.replace("_", "") in f for h in SECRET_HINTS)

    async def create_credential(
        self,
        credential_type: str,
        name: str,
        non_secret_fields_json: str = "{}",
        __user__: dict = None,
        __event_emitter__: Callable[[dict], Awaitable[None]] = None,
        __event_call__: Callable[[dict], Awaitable[Any]] = None,
    ) -> str:
        """
        Legt ein Credential im Konto des Nutzers an. Geheime Werte (Passwörter, Secrets, Tokens, API-Keys)
        werden NICHT über den Chat übergeben, sondern vom Tool in einem eigenen Eingabedialog direkt beim
        Nutzer abgefragt. Vorher get_credential_requirements aufrufen.
        :param credential_type: Interner n8n-Credential-Typname, z. B. 'smtp' oder 'microsoftOutlookOAuth2Api'.
        :param name: Anzeigename, z. B. 'Outlook – Max Mustermann'.
        :param non_secret_fields_json: Nicht-geheime Felder als JSON-Objekt (z. B. host, port, user, clientId).
        """
        try:
            known = self._parse_json(non_secret_fields_json or "{}", "non_secret_fields_json")
            if not isinstance(known, dict):
                raise ValueError("non_secret_fields_json muss ein JSON-Objekt sein.")
            # Geheimnisse dürfen nicht über das LLM kommen
            leaked = [k for k in known if self._is_secret(k) and known[k]]
            if leaked:
                return (
                    "⛔ Geheime Felder dürfen nicht über den Chat übergeben werden: "
                    + ", ".join(leaked)
                    + ". Bitte ohne diese Felder erneut aufrufen – das Tool fragt sie sicher per Dialog ab. "
                    "Der Nutzer sollte das im Chat gepostete Geheimnis außerdem beim Anbieter neu erzeugen."
                )
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                schema = await self._req(c, "GET", f"/credentials/schema/{credential_type}")
                props = schema.get("properties", {}) or {}
                required = schema.get("required", []) or []
                data = dict(known)
                for field in props:
                    if field in data:
                        continue
                    if not (self._is_secret(field) or field in required):
                        continue
                    if __event_call__ is None:
                        return "Dieser Client unterstützt keine Eingabedialoge. Bitte Credential direkt in n8n anlegen."
                    value = await __event_call__(
                        {
                            "type": "input",
                            "data": {
                                "title": f"{name}: {field}",
                                "message": (
                                    f"Bitte Wert für **{field}** eingeben. "
                                    "Der Wert geht direkt an n8n und wird nicht im Chat gespeichert."
                                ),
                                "placeholder": field,
                            },
                        }
                    )
                    if value in (None, False, ""):
                        if field in required:
                            return f"Abgebrochen – Pflichtfeld {field} wurde nicht ausgefüllt."
                        continue
                    data[field] = self._coerce(value, props[field].get("type"))
                await self._status(__event_emitter__, "Lege Credential in n8n an …")
                cred = await self._req(c, "POST", "/credentials", json={"name": name, "type": credential_type, "data": data})
                await self._status(__event_emitter__, "Credential angelegt", True)
        except Exception as e:
            return self._err(e)
        is_oauth = "oauth" in credential_type.lower()
        return json.dumps(
            {
                "result": "created",
                "id": cred["id"],
                "name": cred.get("name"),
                "type": credential_type,
                "url": self._cred_url(cred["id"]),
                "next_step": (
                    "Credential in n8n öffnen und 'Connect my account' / 'Sign in' klicken, um die Anmeldung abzuschließen."
                    if is_oauth else "Kann direkt in Workflows verwendet werden (attach_credential)."
                ),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _coerce(value: Any, typ: Optional[str]) -> Any:
        if typ == "number":
            try:
                return int(value) if re.fullmatch(r"-?\d+", str(value)) else float(value)
            except ValueError:
                return value
        if typ == "boolean":
            return str(value).strip().lower() in ("1", "true", "ja", "yes", "y")
        return value

    async def attach_credential(
        self, workflow_id: str, node_name: str, credential_id: str, __user__: dict = None
    ) -> str:
        """
        Hängt ein vorhandenes Credential an einen Node eines Workflows.
        :param workflow_id: ID des Workflows.
        :param node_name: Exakter Name des Nodes im Workflow.
        :param credential_id: ID des Credentials (aus list_my_credentials oder create_credential).
        """
        try:
            async with self._client(__user__) as c:
                if guard := await self._guard(c):
                    return guard
                creds = await self._paginate(c, "/credentials", {})
                cred = next((x for x in creds if str(x["id"]) == str(credential_id)), None)
                if not cred:
                    return f"Credential {credential_id} nicht gefunden (oder kein Zugriff)."
                wf = await self._req(c, "GET", f"/workflows/{workflow_id}")
                node = next((n for n in wf["nodes"] if n["name"] == node_name), None)
                if not node:
                    return f"Node {node_name!r} nicht im Workflow. Vorhanden: {[n['name'] for n in wf['nodes']]}"
                node.setdefault("credentials", {})[cred["type"]] = {"id": cred["id"], "name": cred["name"]}
                body = {
                    "name": wf["name"],
                    "nodes": wf["nodes"],
                    "connections": wf["connections"],
                    "settings": self._clean_settings(wf.get("settings")),
                }
                await self._req(c, "PUT", f"/workflows/{workflow_id}", json=body)
        except Exception as e:
            return self._err(e)
        return f"✅ Credential „{cred['name']}“ ({cred['type']}) an Node „{node_name}“ gehängt. {self._wf_url(workflow_id)}"

    async def list_my_projects(self, __user__: dict = None) -> str:
        """
        Listet die n8n-Projekte (Enterprise), auf die der Nutzer Zugriff hat.
        """
        try:
            async with self._client(__user__) as c:
                projects = await self._paginate(c, "/projects", {})
        except N8nError as e:
            if e.status in (403, 404):
                return "Projekte können mit diesem Key nicht gelistet werden. Workflows landen im persönlichen Projekt."
            return self._err(e)
        except Exception as e:
            return self._err(e)
        return json.dumps([{"id": p["id"], "name": p.get("name"), "type": p.get("type")} for p in projects], ensure_ascii=False)

    # ------------------------------------------------------------ Tags intern

    async def _tag(self, c: httpx.AsyncClient, wf_id: str, tag_name: str) -> None:
        tags = await self._paginate(c, "/tags", {})
        tag = next((t for t in tags if t.get("name") == tag_name), None)
        if not tag:
            try:
                tag = await self._req(c, "POST", "/tags", json={"name": tag_name})
            except N8nError as e:
                if e.status != 409:
                    raise
                tags = await self._paginate(c, "/tags", {})
                tag = next(t for t in tags if t.get("name") == tag_name)
        await self._req(c, "PUT", f"/workflows/{wf_id}/tags", json=[{"id": tag["id"]}])
