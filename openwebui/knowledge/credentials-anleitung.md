# Anleitung: Zugänge (Credentials) in n8n verbinden

Dieses Dokument gehört in die Wissensbasis des Modells „n8n Workflow Builder“. Es beschreibt das **allgemeine Vorgehen** für jede Art von Zugang. Darunter folgen Kurzrezepte für die häufigsten Anbieter. Für weitere Anbieter einfach einen Abschnitt im gleichen Schema ergänzen.

---

## 1. Welche Art von Zugang ist es?

Das Modell fragt dazu `get_credential_requirements(<typ>)` ab. Im Feld `auth` steht dann eine von drei Arten:

| Art | Beispiele | Wer macht was |
|---|---|---|
| **static** | SMTP, IMAP, Postgres, MySQL, API-Key, Header Auth, Basic Auth, OpenAI | Das Modell legt den Zugang an. Geheime Werte fragt das Tool per Dialog ab. Danach ist er sofort nutzbar. |
| **oauth2** | Microsoft 365, Google, Slack, HubSpot, Salesforce, Zoom, Dropbox | 1) Einmalig: App beim Anbieter registrieren (meist der Admin). 2) Das Modell legt den Zugang mit Client-ID und Secret an. 3) Die Person klickt in n8n auf **Connect my account**. |
| **oauth1** | selten, z. B. Twitter/X (alt) | wie oauth2, nur mit anderer Redirect-URL |

**Redirect-URL für OAuth2** (beim Anbieter eintragen):
`https://<eure-n8n-domain>/rest/oauth2-credential/callback`

---

## 2. Allgemeines Vorgehen bei OAuth2

### Admin-Teil (einmal pro Anbieter)
1. In der Entwickler-/Admin-Konsole des Anbieters eine **App** bzw. einen **OAuth-Client** anlegen.
2. App-Typ: *Web application*.
3. Die **Redirect-URL** von oben eintragen.
4. **Berechtigungen (Scopes)** freigeben. n8n fordert die nötigen Scopes beim Anmelden selbst an. Beim Anbieter müssen sie aber erlaubt sein, und für Firmenkonten ist oft eine Zustimmung durch den Admin nötig.
5. **Client-ID** und **Client Secret** notieren und sicher verteilen, z. B. über einen Passwort-Manager.
6. Empfehlung bei n8n Enterprise: Der Admin legt das Credential einmal an und **teilt** es mit dem Projekt oder den Nutzern (Credential Sharing). Dann muss niemand mit Client-Secrets hantieren.

### Nutzer-Teil
1. Das Modell sagen lassen: „Leg mir ein <Anbieter>-Credential an“. Client-ID und Client Secret werden im Dialog abgefragt, **nicht** im Chat.
2. Den Link zum Credential öffnen, den das Modell schickt.
3. Auf **Connect my account** bzw. **Sign in with …** klicken, mit dem Firmenkonto anmelden und zustimmen.
4. Wenn ein grüner Haken „Account connected“ erscheint, ist der Zugang fertig.
5. Dem Modell sagen: „Häng das Credential an den Workflow“. Oder in n8n den Node öffnen und das Credential auswählen.

---

## 3. Allgemeines Vorgehen bei statischen Zugängen

1. Das Modell fragt die nicht-geheimen Felder im Chat ab, z. B. Host, Port, Benutzername.
2. Passwort, Token oder API-Key fragt das Tool in einem **separaten Eingabedialog** ab. Der Wert geht direkt an n8n und erscheint nicht im Chatverlauf.
3. Der Zugang ist sofort nutzbar.

---

## 4. Kurzrezepte

### Microsoft 365 (Outlook, OneDrive, Excel, Teams, SharePoint, To Do)
- **Credential-Typen:** `microsoftOutlookOAuth2Api`, `microsoftOneDriveOAuth2Api`, `microsoftExcelOAuth2Api`, `microsoftTeamsOAuth2Api`, `microsoftSharePointOAuth2Api`, `microsoftToDoOAuth2Api`
- **Admin:** Entra ID → App registrations → New registration → Redirect URI (Web) eintragen → Certificates & secrets → New client secret → API permissions (Microsoft Graph, Delegated, z. B. `Mail.ReadWrite`, `Mail.Send`, `Calendars.ReadWrite`, `Files.ReadWrite.All`, `Sites.ReadWrite.All`, `ChannelMessage.Send`, `offline_access`) → **Grant admin consent**.
- **Falle:** Bei Single-Tenant-Apps kommt ggf. der Fehler `AADSTS50194`. Dann im Credential, falls das Feld vorhanden ist, die Tenant-ID statt `common` eintragen oder die App als Multitenant registrieren.

### Google Workspace (Gmail, Drive, Sheets, Calendar, Docs)
- **Credential-Typen:** `gmailOAuth2`, `googleDriveOAuth2Api`, `googleSheetsOAuth2Api`, `googleCalendarOAuth2Api`, `googleDocsOAuth2Api`
- **Admin:** Google Cloud Console → Projekt → *APIs & Services* → die benötigten APIs aktivieren (Gmail API, Drive API …) → *OAuth consent screen* (Typ „Internal“ für Workspace) → *Credentials* → *Create OAuth client ID* (Web application) → Redirect-URL eintragen.
- **Falle:** Wurde die API nicht aktiviert, kommt beim ersten Lauf der Fehler `403 … API has not been used`.

### Slack
- **Credential-Typen:** `slackOAuth2Api` (Nutzer) oder `slackApi` (Bot-Token, static)
- **Admin:** api.slack.com/apps → Create App → *OAuth & Permissions* → Redirect URL → Bot Token Scopes, z. B. `chat:write`, `channels:read`, `channels:history` → App im Workspace installieren.
- **Einfacher Weg:** Den Bot User OAuth Token (`xoxb-…`) als `slackApi` anlegen. Der Token wird per Dialog abgefragt.

### E-Mail per SMTP / IMAP
- **Credential-Typen:** `smtp`, `imap`
- **Felder:** host, port (SMTP 587 STARTTLS / 465 SSL, IMAP 993), user, password (Dialog), secure.
- **Falle:** Microsoft 365 und Gmail blockieren Basic Auth oft. Dort lieber die OAuth-Nodes verwenden.

### Beliebige REST-API
- **Credential-Typen:** `httpHeaderAuth` (Header-Name + Wert, z. B. `Authorization` / `Bearer …`), `httpBasicAuth`, `httpQueryAuth`, `oAuth2Api` (generisches OAuth2 mit eigenen Auth-/Token-URLs)
- Wird im Node **HTTP Request** unter *Authentication → Generic Credential Type* ausgewählt.

### Datenbanken
- **Credential-Typen:** `postgres`, `mySql`, `microsoftSql`, `mongoDb`
- **Falle:** Die Datenbank muss vom n8n-Server aus erreichbar sein (Firewall / IP-Freigabe).

---

## 5. Typische Fehler

| Meldung | Ursache | Lösung |
|---|---|---|
| `redirect_uri_mismatch` / `AADSTS50011` | Redirect-URL beim Anbieter falsch | URL exakt wie oben eintragen (https, keine Slash am Ende) |
| `invalid_client` | Client-ID oder Secret falsch bzw. abgelaufen | Secret neu erzeugen, Credential aktualisieren |
| `insufficient permissions` / `403` | Scope fehlt oder Admin-Zustimmung fehlt | Scope beim Anbieter freigeben, Admin-Zustimmung erteilen |
| Workflow lässt sich nicht aktivieren | Ein Node hat kein Credential | Rot markierte Nodes in n8n öffnen und Credential auswählen |
| Token läuft nach einiger Zeit ab | `offline_access` bzw. Refresh-Token fehlt | Scope ergänzen, neu verbinden |
