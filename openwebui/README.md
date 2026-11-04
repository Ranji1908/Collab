# n8n Workflow Builder für Open WebUI: Einrichtung

```
openwebui/
├─ tools/n8n_workflows.py                      → Open WebUI → Workspace → Tools
├─ models/n8n-workflow-builder/system-prompt.md → System-Prompt des Modells
└─ knowledge/credentials-anleitung.md          → Knowledge-Collection des Modells
tests/test_n8n_workflows.py                    → Tests gegen simulierte n8n-API
```

## 1. n8n vorbereiten (Admin)
1. Prüfen, dass die Public API aktiv ist: `N8N_PUBLIC_API_DISABLED` darf nicht `true` sein.
2. `N8N_EDITOR_BASE_URL` und `WEBHOOK_URL` auf die öffentliche URL setzen. Das ist nötig für OAuth-Callbacks.
3. Gefährliche Nodes serverseitig sperren, z. B.:
   `NODES_EXCLUDE=["n8n-nodes-base.executeCommand","n8n-nodes-base.ssh","n8n-nodes-base.readWriteFile","n8n-nodes-base.localFileTrigger"]`
4. Alle normalen Nutzer bekommen die Rolle **Member**. Keys von Owner/Admin lehnt das Tool standardmäßig ab.
5. Enterprise: API-Key-Scopes für Member erlauben. Empfohlene Scopes stehen in der Setup-Anleitung des Tools (`SETUP_HINT`).

## 2. Tool installieren
1. Open WebUI → **Workspace → Tools → +** → Inhalt von `tools/n8n_workflows.py` einfügen → Speichern.
2. Beim Tool auf das **Zahnrad (Valves)** klicken:
   - `n8n_base_url`: interne URL, z. B. `http://n8n:5678`
   - `n8n_public_url`: z. B. `https://n8n.firma.de`
   - übrige Werte nach Bedarf (Allowlist, Aktivieren erlauben, Tag)
3. Sichtbarkeit des Tools: **Public** bzw. für die Gruppe aller Mitarbeiter.

## 3. Knowledge anlegen
Unter **Workspace → Knowledge → +** eine Collection „n8n Builder“ anlegen. Hochladen:
- `knowledge/credentials-anleitung.md`
- 5 bis 10 exportierte Beispiel-Workflows (JSON aus n8n: „Download“), die nachweislich laufen. Sie zeigen dem Modell aktuelle Node-Typen und -Versionen. Das ist der größte Hebel für gute Ergebnisse.

## 4. Modell anlegen
**Workspace → Models → +**
- Name: `n8n Workflow Builder`
- Basismodell: ein starkes Modell mit zuverlässigem Function Calling
- System-Prompt: Inhalt von `models/n8n-workflow-builder/system-prompt.md`
- Tools: **n8n Workflows** anhaken
- Knowledge: Collection „n8n Builder“
- Advanced Params: **Function Calling = Native** (falls das Basismodell es unterstützt)
- Sichtbarkeit: **Public**

## 5. Für die Nutzer
1. Modell „n8n Workflow Builder“ auswählen.
2. Beim ersten Mal erklärt das Modell, wie man den eigenen n8n-API-Key erzeugt und einträgt (Werkzeug-Symbol → n8n Workflows → Zahnrad).
3. Danach einfach beschreiben, was automatisiert werden soll.

## Tests
```bash
pip install httpx pydantic pytest pytest-asyncio
pytest
```
