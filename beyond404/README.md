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

## Deploy

Live auf Hostinger-Webhosting (Konto u283350977, Website beyond404.io).
beyond404.de leitet per 301 auf beyond404.io weiter.

1. Inhalt von `site/` als ZIP packen (inklusive `.htaccess`).
2. ZIP über den Dateimanager oder die Hostinger-API nach `public_html` hochladen.
3. „Deploy static site archive“ ausführen, das entpackt und ersetzt den Inhalt.

`Dockerfile`, `nginx.conf`, `docker-compose.yml` und `Caddyfile.snippet` bleiben als Alternative für den VPS.

## Vor dem Livegang (aus dem Briefing)

- [ ] Spalte „Standard bisher“ und alle Zahlen prüfen (492 Kriterien, 594 Programme)
- [ ] Öffentliche Prototypen auf interne Daten prüfen
- [ ] Markenprüfung EUIPO/DPMA
