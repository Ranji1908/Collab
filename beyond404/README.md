# beyond404.io

Statische One-Page-Website nach dem [Website-Briefing](https://claude.ai/artifact/5xaoX8ifFBXE4GtQuwojrq).
Kein Backend, keine Cookies, keine externen Schriften oder Skripte.

## Struktur

- `site/` – die Website (`index.html`, `styles.css`, `main.js`, Impressum, Datenschutz, 404)
- `Dockerfile`, `nginx.conf` – Container, der `site/` ausliefert
- `docker-compose.yml` – Container im Caddy-Netzwerk
- `Caddyfile.snippet` – Eintrag für Caddy, inkl. Weiterleitung `beyond404.de` → `beyond404.io`

## Lokal ansehen

```sh
cd site && python3 -m http.server 8080
```

## Deploy auf dem VPS

1. DNS: A-/AAAA-Records von `beyond404.io`, `www.beyond404.io`, `beyond404.de`, `www.beyond404.de` bei Hostinger von den Parking-Nameservern auf die VPS-IP setzen.
2. Netzwerkname in `docker-compose.yml` an das Caddy-Netzwerk anpassen, dann `docker compose up -d --build`.
3. `Caddyfile.snippet` in die Caddyfile übernehmen und Caddy neu laden. SSL kommt automatisch.

## Vor dem Livegang (aus dem Briefing)

- [ ] Kontaktadresse festlegen – aktuell Platzhalter `hello@beyond404.io` in `site/index.html`
- [ ] Impressum und Datenschutz ausfüllen (Platzhalter in eckigen Klammern) und prüfen lassen
- [ ] Spalte „Standard bisher“ und alle Zahlen prüfen (492 Kriterien, 594 Programme)
- [ ] Öffentliche Prototypen auf interne Daten prüfen
- [ ] Markenprüfung EUIPO/DPMA
