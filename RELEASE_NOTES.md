# Mythic Walker 0.1.1 Beta 1

Erste GitHub-Vorabversion: eigenständige Windows-EXE mit Status-Widget rechts unten,
automatischem Browserstart und Bridge-Kopplung. Beta-Updates werden beim Start aus
GitHub Releases geladen und per SHA-256 gegen das Manifest geprüft.

## Movement und Tasten

- X: X an alle gehookten Clients (Scope in den Settings änderbar).
- F8: XYZ zum aktiven/Leader-Client synchronisieren.
- F7: Navmap Quest-Teleport für den aktiven Client.
- F6: Navmap Quest-Teleport für alle; gleichzonige Clients nutzen standardmäßig das Leader-Ziel, andere ihr eigenes.
- F5: konfigurierten Geschwindigkeitswert ein-/ausschalten; Originalwerte werden beim Trennen wiederhergestellt.
- 9: Auto-Combat, F4: Auto-Dialog, F3: Auto-Questing, F2: Auto-Sigil.
- F1: Freecam, Shift+F1: Charakter zur Freecam teleportieren.
- Ctrl+Alt+F8: Skript und alle Automatiken stoppen.

Globale Shortcuts sind nur bei fokussiertem, gehooktem Wizard101 aktiv.
Alle Aktionen sind auch in der Weboberfläche bedienbar. Scope, Quest-Ziele, Navmap-
Zeitlimit, Speed, Kampfregeln, Laufzeit und Dialog-/Quest-/Sigil-Optionen sind editierbar.

## Beta-Funktionsumfang

Navmap nutzt direkten Teleport, bei Bedarf `zone.nav`-Stützpunkte und einen begrenzten
Fallback aus Deimos. Kein kompletter neuer Collision-Mesh-Navigator.
Auto-Combat spielt die erste verfügbare Regel aus einer Prioritätenliste, genau eine
Auswahl pro Runde. Regeln: Kartenname@self/enemy/none, any<aoe>@enemy, pass.
Auto-Questing folgt dem aktuellen Ziel, interagiert und bedient Dialoge. Auto-Sigil
merkt sich Position und Zone beim Start und kann nach Rückkehr erneut eintreten.
Alle Clients zum Start am Sigil positionieren (bei Bedarf vorher F8).

Komplexe Weltübergänge, Dungeon-Ausgänge, Auswahldialoge und Questtypen können manuelle
Schritte benötigen. Kampf separat über 9 einschalten. Verzauberungen und die vollständige
Deimos-Playstyle-Sprache sind noch nicht integriert. Spielbetrieb auf Windows ist zusätzlich
zu den automatisierten Tests zu bestätigen; die Release-Pipeline prüft die gebaute EXE
mit einem nativen Fenster-Smoke-Test.

Quellcode unter GPL-3.0; Navmap-/Boost-Hinweise siehe THIRD_PARTY_NOTICES.md.
