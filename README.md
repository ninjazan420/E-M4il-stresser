# safe email load-test kit 📨

dieses kit simuliert hohe eingangs-last auf einem smtp-catch-all, z. b. mit *mailpit*.

## inhalt
- `docker-compose.yml` — startet **mailpit** (smtp: 1025, ui: 8025)
- `sender.py` — generiert nachrichten und sendet sie **nur** an 127.0.0.1
- `.env.example` — beispielkonfiguration

## voraussetzungen
- docker + docker compose
- python 3.9+

## start
```bash
# 1) mailpit starten
docker compose up -d

# 2) config anlegen
cp .env.example .env
# optional: werte anpassen

# 3) last erzeugen
python3 sender.py --messages 5000 --concurrency 20 --rate 0
# oder mit .env werten einfach:
python3 sender.py
```

öffne jetzt `http://localhost:8025` und beobachte die eingehenden mails.
`sender.py` schreibt außerdem eine `metrics.jsonl` mit einer zusammenfassung.

## optionen
```
python3 sender.py -h
```
wichtige flags:
- `--messages` gesamtzahl
- `--concurrency` anzahl worker threads
- `--rate` msg/s gesamt
- `--attachment` fügt zufällige binär-anhänge hinzu

## sicherheit
- nutze das kit **nur** für eigene labs/aliases
- kein einsatz gegen fremde postfächer

## cleanup & auswertung
- in mailpit kannst du **bulk delete** nutzen
- schau dir die `metrics.jsonl` an, letzte zeile enthält die zusammenfassung
- variiere `MIN_BYTES/MAX_BYTES`, um unterschiedliche payloadgrößen zu simulieren

## härten deines echten postfachs
- **double opt-in** überall erzwingen
- **rate limit** und **greylisting** am mta (postfix, rspamd)
- **captcha** auf web-formularen
- **filterregeln** für „confirm your subscription“ & „verify your email“
- **aliases** und **plus-addressing** verwenden, kompromittierte aliases rotieren
```

> rechtlicher hinweis: verwende dieses kit nicht, um fremde systeme zu beeinträchtigen. du trägst die verantwortung für deinen einsatz.