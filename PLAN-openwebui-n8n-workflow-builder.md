# Plan: „n8n Workflow Builder“ als Open-WebUI-Modell

Ziel: Ein Modell in Open WebUI, das **alle Nutzer** verwenden können. Man beschreibt in normaler Sprache, was automatisiert werden soll, und das Modell legt daraus einen **n8n-Workflow im eigenen n8n-Konto** an. Jeder Nutzer hinterlegt dafür einmal seinen eigenen n8n-API-Key. Damit sieht und ändert jeder nur seine eigenen Workflows.

---

## 1. Architektur im Überblick

```
┌──────────────────────── Open WebUI ────────────────────────┐
│                                                            │
│  Modell „n8n Workflow Builder“  (für alle sichtbar)        │
│   ├─ Basis-LLM (z. B. Claude / GPT / lokales Modell)       │
│   ├─ System-Prompt (Regeln, n8n-JSON-Format, Anleitungen)  │
│   ├─ Knowledge: Anleitungen (M365, Google, Slack …)        │
│   └─ Tool „n8n_workflows“                                  │
│        ├─ Valves      (Admin): N8N_BASE_URL, Allowlist …   │
│        └─ UserValves  (pro Nutzer): n8n API-Key            │
│                                                            │
└──────────────┬─────────────────────────────────────────────┘
               │  HTTPS, Header: X-N8N-API-KEY = Key des Nutzers
               ▼
┌──────────────────────── n8n ───────────────────────────────┐
│  Public REST API  /api/v1/...                              │
│  → Workflow landet im persönlichen Projekt des Key-Owners  │
│  → Credentials (OAuth) verbindet der Nutzer selbst in n8n  │
└────────────────────────────────────────────────────────────┘
```

**Der wichtigste Punkt:** Die Trennung der Nutzer macht **n8n selbst**, nicht Open WebUI. Ein n8n-API-Key hat dieselben Rechte wie der Nutzer, dem er gehört. Wenn Open WebUI jede Anfrage mit dem Key des gerade chattenden Nutzers schickt, kann niemand fremde Workflows sehen. Das gilt nicht für Owner-/Admin-Keys (siehe Abschnitt 7).

**Wo der Key gespeichert wird:** Open-WebUI-Tools haben `UserValves`. Das sind Einstellungen, die **pro Nutzer** gespeichert werden. Jeder Nutzer trägt seinen Key dort einmal ein: im Chat über das Werkzeug-Symbol → Tool „n8n_workflows“ → Zahnrad. Das Tool liest den Key bei jedem Aufruf über `__user__["valves"]`. So landet der Key nie im Chatverlauf und nie beim LLM.

---

## 2. Voraussetzungen (einmalig, Admin)

### n8n
1. n8n muss selbst gehostet sein oder ein Tarif mit **Public API**. Die API darf nicht deaktiviert sein (`N8N_PUBLIC_API_DISABLED` nicht auf `true`).
2. `N8N_EDITOR_BASE_URL` / `WEBHOOK_URL` müssen korrekt auf die öffentliche URL zeigen. Das ist wichtig für OAuth-Callbacks (z. B. Microsoft).
3. Jeder Nutzer hat ein **eigenes n8n-Konto** mit der Rolle *Member*, nicht Owner/Admin.
4. Optional, je nach Lizenz: API-Key-Scopes. Damit lässt sich der Key auf `workflow:*` und `credential:create` beschränken.

### Open WebUI
1. Eine aktuelle Version mit Tools, `UserValves` und Workspace-Modellen.
2. Der Open-WebUI-Server muss n8n über das Netzwerk erreichen, z. B. per Docker-Netz `http://n8n:5678`.
3. Ein Basis-LLM, das zuverlässig **Function Calling** und **lange JSON-Ausgaben** kann. Kleine lokale Modelle scheitern oft an n8n-JSON.

---

## 3. Bausteine

### 3.1 Tool `n8n_workflows` (Python, in Open WebUI unter Workspace → Tools)

Funktionen, die das LLM aufrufen kann:

| Funktion | n8n-Endpoint | Zweck |
|---|---|---|
| `check_connection()` | `GET /api/v1/workflows?limit=1` | Prüft, ob der Key gesetzt ist und funktioniert. Sonst kommt eine Anleitung zum Einrichten. |
| `list_my_workflows(search)` | `GET /api/v1/workflows` | Zeigt die eigenen Workflows (Name, ID, aktiv ja/nein, Link). |
| `get_workflow(id)` | `GET /api/v1/workflows/{id}` | Lädt einen bestehenden Workflow, um ihn zu ändern. |
| `create_workflow(name, nodes_json, connections_json)` | `POST /api/v1/workflows` | Legt den Workflow **inaktiv** an, mit Tag `openwebui`. |
| `update_workflow(id, …)` | `PUT /api/v1/workflows/{id}` | Ändert einen Workflow. |
| `activate_workflow(id)` / `deactivate_workflow(id)` | `POST /api/v1/workflows/{id}/activate` bzw. `/deactivate` | Schaltet einen Workflow an oder aus, nur nach ausdrücklicher Bestätigung. In neueren n8n-Versionen heißt das „Publish“. |
| `get_credential_schema(type)` | `GET /api/v1/credentials/schema/{type}` | Zeigt, welche Felder ein Credential-Typ braucht. |
| `list_executions(workflow_id)` | `GET /api/v1/executions` | Zeigt die letzten Läufe und Fehler, zum Debuggen. |

Prüfungen im Tool, bevor etwas an n8n geht:
- Ist der Key vorhanden? Wenn nicht, gibt es eine Anleitung statt eines Fehlers.
- Ist das JSON gültig? Hat jeder Node `id`, `name`, `type`, `typeVersion`, `position` und `parameters`?
- Ist jeder Node-Typ in der **Allowlist** des Admins? Riskante Nodes wie `executeCommand` oder `ssh` sind standardmäßig gesperrt.
- Ein Workflow wird nie automatisch aktiviert.
- Als Antwort kommen immer die Workflow-ID und ein Direktlink zurück: `{N8N_PUBLIC_URL}/workflow/{id}`.

Grundgerüst:

```python
"""
title: n8n Workflows
description: Legt n8n-Workflows im Konto des jeweiligen Nutzers an.
version: 0.1.0
"""
import json, httpx
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):                     # nur Admin
        n8n_base_url: str = Field("http://n8n:5678", description="Interne URL")
        n8n_public_url: str = Field("https://n8n.example.de", description="Für Links")
        allowed_node_prefixes: str = "n8n-nodes-base.,@n8n/n8n-nodes-langchain."
        blocked_nodes: str = "n8n-nodes-base.executeCommand,n8n-nodes-base.ssh"

    class UserValves(BaseModel):                 # pro Nutzer
        n8n_api_key: str = Field("", description="Dein n8n API-Key (n8n → Settings → n8n API)")

    def __init__(self):
        self.valves = self.Valves()

    def _client(self, __user__):
        key = (__user__ or {}).get("valves") and __user__["valves"].n8n_api_key
        if not key:
            raise ValueError("NO_KEY")
        return httpx.AsyncClient(
            base_url=self.valves.n8n_base_url.rstrip("/") + "/api/v1",
            headers={"X-N8N-API-KEY": key}, timeout=30)

    async def list_my_workflows(self, search: str = "", __user__: dict = None) -> str:
        """Listet die n8n-Workflows des aktuellen Nutzers."""
        try:
            async with self._client(__user__) as c:
                r = await c.get("/workflows", params={"limit": 100})
                r.raise_for_status()
        except ValueError:
            return SETUP_HINT
        wfs = [w for w in r.json()["data"] if search.lower() in w["name"].lower()]
        return json.dumps([{"id": w["id"], "name": w["name"], "active": w["active"],
                            "url": f'{self.valves.n8n_public_url}/workflow/{w["id"]}'} for w in wfs])

    async def create_workflow(self, name: str, nodes_json: str, connections_json: str,
                              __user__: dict = None, __event_emitter__=None) -> str:
        """Legt einen neuen (inaktiven) n8n-Workflow an.
        :param name: Name des Workflows
        :param nodes_json: JSON-Array der n8n-Nodes
        :param connections_json: JSON-Objekt der n8n-Connections
        """
        nodes = json.loads(nodes_json); conns = json.loads(connections_json)
        # … Validierung + Allowlist hier …
        body = {"name": name, "nodes": nodes, "connections": conns,
                "settings": {"executionOrder": "v1"}}
        async with self._client(__user__) as c:
            r = await c.post("/workflows", json=body)
        if r.status_code >= 400:
            return f"Fehler von n8n ({r.status_code}): {r.text[:800]}"   # LLM kann korrigieren
        wf = r.json()
        return f'Angelegt: {wf["name"]} (ID {wf["id"]}) → {self.valves.n8n_public_url}/workflow/{wf["id"]}'

SETUP_HINT = """Kein n8n API-Key hinterlegt. So geht's:
1. In n8n einloggen → unten links Profil → Settings → n8n API → „Create an API key“.
2. Key kopieren.
3. Hier im Chat: Werkzeug-Symbol → „n8n Workflows“ → Zahnrad → Key einfügen → Speichern."""
```

Wenn n8n einen Fehler meldet, gibt das Tool den Fehlertext (gekürzt) an das LLM zurück. Das LLM korrigiert dann selbst das JSON und versucht es ein- oder zweimal neu.

### 3.2 Workspace-Modell „n8n Workflow Builder“

Anlegen unter Workspace → Models → New:
- **Basismodell:** ein starkes Modell mit Tool-Calling.
- **Tools:** `n8n_workflows` aktivieren.
- **Knowledge:** die Anleitungen aus Abschnitt 4 als Dokumente hochladen. Dazu einige Beispiel-Workflow-JSONs, die nachweislich funktionieren. Das ist die beste Vorlage für das LLM.
- **Sichtbarkeit:** *Public*, oder für eine Gruppe „Alle Mitarbeiter“.
- **Prompt-Vorschläge:** z. B. „Neue Mails mit Anhang automatisch in OneDrive speichern“ oder „Jeden Montag eine Teams-Nachricht mit offenen Aufgaben“.

Kern des System-Prompts:

```
Du bist ein n8n-Workflow-Architekt. Ablauf:
1. Rufe zuerst check_connection auf. Fehlt der Key, gib die Einrichtungsanleitung aus und stoppe.
2. Kläre mit maximal 3 Rückfragen: Auslöser, Datenquellen/-ziele, Bedingungen, gewünschtes Ergebnis.
3. Beschreibe den geplanten Workflow kurz in Stichpunkten und hole ein „OK“ ein.
4. Erzeuge gültiges n8n-JSON (nodes + connections). Verwende nur Standard-Nodes.
   Credentials NICHT erfinden – lasse das Feld "credentials" weg.
5. Rufe create_workflow auf. Bei Fehlern: korrigieren und erneut versuchen (max. 2x).
6. Gib dem Nutzer: Link zum Workflow + Schritt-für-Schritt-Anleitung, welche
   Credentials er in n8n verbinden muss (aus der Knowledge-Base).
7. Aktiviere Workflows nie ohne ausdrückliche Bestätigung.
Sprache: Deutsch, verständlich für Nicht-Techniker.
```

---

## 4. Credentials und Anleitungen (z. B. Microsoft 365)

**Grundsatz:** OAuth-Verbindungen wie Microsoft, Google oder Slack kann **das Modell nicht selbst anlegen**. Der Nutzer muss sich einmal in n8n im Browser anmelden und zustimmen. Das Modell erstellt deshalb den Workflow **ohne Credentials** und schickt eine genaue Anleitung mit. Der Nutzer klickt in n8n auf den rot markierten Node, wählt „Create new credential“ und meldet sich an.

Damit das für normale Nutzer einfach bleibt, sollte der **Admin die App-Registrierung einmal zentral** machen. Die Nutzer brauchen dann nur Client-ID und Secret einzutragen, oder der Admin teilt ein fertiges Credential.

### 4.1 Microsoft 365 (Outlook, OneDrive, Excel, Teams, SharePoint): Admin-Teil, einmalig

1. **Azure-/Entra-Portal** → *App registrations* → *New registration*
   - Name: `n8n`
   - Supported account types: *Accounts in this organizational directory only* (Single Tenant). Funktioniert die Anmeldung damit in eurer n8n-Version nicht, *Multitenant* wählen (siehe Hinweis unten).
   - Redirect URI (Web): `https://<eure-n8n-domain>/rest/oauth2-credential/callback`
2. **Certificates & secrets** → *New client secret* → den **Value** sofort kopieren. Er wird nur einmal angezeigt.
3. **API permissions** → Microsoft Graph → *Delegated permissions*, je nach Bedarf:
   - immer: `User.Read`, `offline_access`
   - Outlook: `Mail.ReadWrite`, `Mail.Send`, `Calendars.ReadWrite`, `Contacts.Read`
   - OneDrive/Excel: `Files.ReadWrite.All`
   - SharePoint: `Sites.ReadWrite.All`
   - Teams: `Chat.ReadWrite`, `ChannelMessage.Send`, `Team.ReadBasic.All`, `Channel.ReadBasic.All`
   - To Do / Planner: `Tasks.ReadWrite`
4. **Grant admin consent for <Tenant>** klicken. Dann muss nicht jeder Nutzer einzeln zustimmen.
5. Client-ID (*Application (client) ID*) und Secret sicher an die Nutzer weitergeben, oder fertige Credentials teilen (n8n Enterprise: Credential Sharing).

> **Hinweis zu Single Tenant:** Einige Microsoft-Credentials in n8n nutzen fest den `common`-Endpunkt. Bei einer Single-Tenant-App kommt dann der Fehler `AADSTS50194`. Lösungen: App als *Multitenant* registrieren, oder in n8n ein generisches **OAuth2 API**-Credential nutzen mit
> Auth-URL `https://login.microsoftonline.com/<TENANT_ID>/oauth2/v2.0/authorize`,
> Token-URL `https://login.microsoftonline.com/<TENANT_ID>/oauth2/v2.0/token`.
> Das sollte vor dem Rollout mit eurer n8n-Version getestet werden.

### 4.2 Microsoft 365: Nutzer-Teil (diesen Text schickt das Modell mit)

1. Den Link zum Workflow öffnen.
2. Auf den Node mit dem roten Warndreieck klicken, z. B. „Microsoft Outlook“.
3. Bei *Credential* → **Create new credential** wählen.
4. **Client ID** und **Client Secret** eintragen (vom Admin bzw. aus dem Intranet).
5. **Connect my account** → mit dem Firmenkonto anmelden → zustimmen.
6. Speichern. Diese Schritte für jeden weiteren Microsoft-Node wiederholen. Dasselbe Credential kann wiederverwendet werden.
7. Oben **Test workflow** klicken. Wenn alles klappt, dem Modell „aktivieren“ schreiben.

### 4.3 Weitere Anleitungen für die Knowledge-Base (im selben Format)

- Google Workspace (Gmail, Drive, Sheets, Calendar): Google Cloud Console, OAuth Consent Screen, Client ID, gleiche Redirect-URI
- Slack (App erstellen, Bot Token Scopes)
- SMTP/IMAP (einfach: Host, Port, Benutzer, Passwort)
- HTTP Request mit API-Key (Header Auth)
- Datenbanken (Postgres/MySQL, inkl. Firewall-Freigabe)

Jede Anleitung bekommt die gleichen Abschnitte: **Admin-Teil**, **Nutzer-Teil**, **benötigte Berechtigungen pro Node**, **typische Fehler**. Dann kann das Modell gezielt den passenden Abschnitt zitieren.

---

## 5. Ablauf aus Nutzersicht

1. Der Nutzer öffnet das Modell „n8n Workflow Builder“.
2. Ist noch kein Key hinterlegt, antwortet das Modell mit der 3-Schritte-Anleitung zum API-Key.
3. Der Nutzer schreibt z. B.: *„Wenn eine Mail mit ‚Rechnung‘ im Betreff kommt, speichere den PDF-Anhang in OneDrive/Buchhaltung und schick mir eine Teams-Nachricht.“*
4. Das Modell stellt bis zu 3 Rückfragen und zeigt dann den Plan: Outlook-Trigger → Filter → OneDrive Upload → Teams Message.
5. Nach dem „OK“ des Nutzers legt das Modell den Workflow an und schickt den Link plus die Microsoft-Anleitung.
6. Der Nutzer verbindet die Credentials in n8n, testet und lässt den Workflow vom Modell aktivieren.
7. Später: *„Zeig meine Workflows“* oder *„Ändere den Rechnungs-Workflow, dass auch .xlsx gespeichert wird“*. Das Modell nutzt dafür `get_workflow` und `update_workflow`.

---

## 6. Umsetzung in Phasen

| Phase | Inhalt | Ergebnis |
|---|---|---|
| **0 – Vorbereitung** (½ Tag) | n8n-API prüfen, Nutzerrollen prüfen (alle *Member*), Netzwerk Open WebUI → n8n, Test-Key | `curl -H "X-N8N-API-KEY: …" https://n8n/api/v1/workflows` funktioniert |
| **1 – MVP-Tool** (1–2 Tage) | Tool mit `check_connection`, `list_my_workflows`, `create_workflow`, UserValves | Ein Testnutzer legt per Chat einen einfachen Workflow an (Schedule → HTTP → Set) |
| **2 – Modell & Prompt** (1 Tag) | Workspace-Modell, System-Prompt, 5–10 Beispiel-Workflows als Knowledge | Natürliche Sprache wird zuverlässig zu gültigem JSON |
| **3 – Integrationen** (2–3 Tage) | Azure-App-Registrierung, Anleitungen M365/Google/SMTP, Beispiel-Workflows je Integration | Outlook-/OneDrive-/Teams-Workflow läuft Ende-zu-Ende |
| **4 – Absicherung** (1–2 Tage) | Node-Allowlist, Key-Verschlüsselung, Logging, Rate Limit, `update`/`activate`/`executions` | Security-Review bestanden |
| **5 – Pilot & Rollout** | 3–5 Pilotnutzer → Feedback → Prompt/Knowledge nachschärfen → Freigabe für alle | Modell öffentlich, kurze Intranet-Anleitung |

---

## 7. Sicherheit und Fallstricke

- **Owner-/Admin-Keys sehen alles.** Ein API-Key eines n8n-Owners oder -Admins sieht alle Workflows der Instanz. Die normalen Nutzer müssen deshalb *Member* sein. Optional prüft das Tool beim ersten Aufruf die Rolle über `GET /api/v1/users/me`, falls verfügbar, und warnt.
- **Speicherung der Keys:** `UserValves` liegen im Klartext in der Open-WebUI-Datenbank. Andere Nutzer sehen sie nicht, Datenbank-Admins schon. Empfehlung: Das Tool verschlüsselt den Key mit einem Server-Secret (`Fernet`, Secret in den Admin-Valves bzw. als Umgebungsvariable). Zusätzlich API-Key-Scopes und ein Ablaufdatum in n8n nutzen.
- **Key nie ans LLM:** Der Key wird nur im Tool gelesen und nie zurückgegeben oder geloggt.
- **Gefährliche Nodes sperren:** `Execute Command`, `SSH`, `Code` mit Dateizugriff usw. per Allowlist ausschließen. Zusätzlich auf n8n-Seite `NODES_EXCLUDE` setzen. Das ist die eigentliche Absicherung.
- **Nie automatisch aktivieren.** Workflows werden inaktiv angelegt, eine Aktivierung gibt es nur nach Bestätigung.
- **n8n-Versionen:** Die API-Felder unterscheiden sich zwischen den Versionen, z. B. Publish vs. Activate oder Read-only-Felder bei `PUT`. Das Tool entfernt vor `PUT` Felder wie `id`, `active`, `tags`, `createdAt`. Nach jedem n8n-Update einen kurzen Smoke-Test fahren.
- **Projekte (n8n Enterprise):** Workflows landen im persönlichen Projekt. Sollen Teams gemeinsame Projekte nutzen, lässt sich `projectId` als optionaler Parameter ergänzen.
- **LLM-Qualität:** Die Zuverlässigkeit hängt stark von Beispiel-Workflows in der Knowledge-Base ab. Lieber 10 gute Vorlagen als ein langer Prompt.

---

## 8. Alternative: n8n-MCP-Server statt eigenem Tool

Neuere n8n-Versionen haben einen eingebauten **MCP-Server** mit persönlichen Zugriffstokens pro Nutzer. Er bringt fertige Funktionen zum Bauen, Validieren und Testen von Workflows mit. Open WebUI kann MCP-Server als Tool-Server einbinden.

- **Vorteil:** Workflow-Validierung und Node-Wissen kommen direkt aus n8n. Die JSON-Qualität ist dadurch deutlich besser.
- **Problem:** Tool-Server in Open WebUI haben meist **einen** Auth-Header für alle Nutzer. Ein Token pro Nutzer ist ohne Zwischenschicht schwierig.
- **Möglicher Weg später:** Ein kleiner Proxy, der das Open-WebUI-Nutzer-Token (Header `X-OpenWebUI-User-Id` bzw. weitergeleitete Session) dem jeweiligen n8n-MCP-Token zuordnet.

**Empfehlung:** Mit dem eigenen Tool und `UserValves` starten (Abschnitt 3). Das ist einfach, transparent und pro Nutzer sauber getrennt. Den MCP-Weg prüfen, sobald das MVP läuft.

---

## 9. Nächste Schritte

1. Versionen von Open WebUI und n8n mitteilen sowie die n8n-Lizenz (Community / Enterprise wegen Projekten und Scopes).
2. Klären, wer in Azure eine App-Registrierung anlegen und Admin-Consent erteilen darf.
3. Danach: Tool-Code (Phase 1) vollständig ausprogrammieren und gegen eine Test-Instanz prüfen.
