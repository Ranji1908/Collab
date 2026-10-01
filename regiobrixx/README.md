# Regiobrixx — Landing Page

Statische Landingpage für **Regiobrixx by Hermibricks** (individuelle Klemmbaustein-Sets
für touristische Destinationen). Inhalte stammen aus dem Konzeptdokument „Regiobrixx".

## Dateien

| Datei | Inhalt |
|---|---|
| `index.html` | Komplette Seite (Hero, Modelle, Ablauf, Pakete, Vorteile, Vertrieb, Über uns, Kontakt) |
| `styles.css` | Design-Tokens, Layout, Komponenten, Responsive- und Print-Regeln |
| `main.js` | Mobile-Navigation, Parallax, Scroll-Reveal, Kontaktformular |
| `images/` | Produktfotos der bestehenden Modelle |

## Lokal ansehen

Einfach `index.html` im Browser öffnen — kein Build, keine Abhängigkeiten.
Schriften (Instrument Serif, Inter) kommen von Google Fonts; ohne Internet greifen System-Fallbacks.

## Gestaltung

Ruhiges, redaktionelles Layout: warmes Off-White (`#FBFAF8`), Serif-Headlines
(Instrument Serif) über Inter-Fließtext, Haarlinien statt Rahmen und Schatten,
keine Flächenfarben. Die Farbe kommt ausschließlich aus den Produktfotos.
Alle Maße liegen als Custom Properties am `:root` in `styles.css`.

### Parallax

Jedes Bild mit `data-parallax="<faktor>"` sitzt in einem `.parallax`-Rahmen mit
fester Seitenratio. Der Rahmen schneidet das Bild oben und unten um `--range`
zu kurz ab; `main.js` verschiebt es beim Scrollen innerhalb dieses Spielraums
über `--shift`. Der Faktor steuert die Stärke (0.35 dezent bis 0.7 kräftig).
Ohne JavaScript oder bei `prefers-reduced-motion: reduce` bleiben die Bilder
mittig stehen — das Layout ändert sich dadurch nicht.

## Noch anzupassen

- **E-Mail-Adresse:** Platzhalter `hallo@regiobrixx.de` in `index.html` und `main.js` ersetzen.
- **Kontaktformular:** öffnet aktuell das Mail-Programm (`mailto:`) mit vorausgefüllter Nachricht.
  Für serverseitigen Versand das `submit`-Handling in `main.js` gegen einen Form-Endpoint tauschen.
- **Impressum/Datenschutz:** Links in der Fußzeile ergänzen.
- **Bilder:** für Produktion zusätzlich als WebP/AVIF ausliefern.
