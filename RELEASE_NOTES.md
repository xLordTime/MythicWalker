## 0.1.1 Beta 9 · Deimos Expertmode und Script Studio

- Originaler Deimos-Tokenizer, Parser, Semantik und Compiler, GPL-3.0, fest auf Commit d7ef56eb51c5b5316cadba40ca554ec442a5dcee. DE-WizWalker und Hooks bleiben auf dem bisherigen Stand.
- Neue Bridge-VM: con/setvar, if/elif/else, and/or/not, Prozentvergleiche, Variablen/Zähler, Timer, blocks/calls/mixins, return/break, restart/kill, until-Überwachung, client ranges, except, any/sameany und parallele Befehle. Kein Python eval/exec.
- Wiki-Aliasse ergänzt: loop N times, addone/minusone/reset, Timer, setyaw, nav, friendtp mit Anführungszeichen und parallele sendkey-Befehle ohne explizite Dauer.
- Zusätzliche Live-Aktionen: relative TP, Client-TP, Laufen mit begrenzten und sauber freigegebenen Tastendrücken, UI-Pfade, virtueller Cursor, Kampf/Dialog/Frei/Zone/Fenster warten, Tränke und Relog.
- Stats, Windowtext/Windownum, Quest-Tracking über vorhandene DE-WizWalker-APIs. Friend-TP verwendet die gepinnte WizWalker-Freundeslistenlogik.
- Zwölf Katalogdateien werden erfolgreich mit dem neuen Compiler übersetzt. Jede wird bei aktiver Bridge erneut geprüft. Spielablauf, Bedingungen des Autors, Decks und Startzone müssen zusätzlich im DE-Spiel geprüft werden.
- Standardbibliothek wird nach Bedarf mit transitiven Abhängigkeiten eingebunden; Expertmode-Blöcke lassen sich ebenfalls speichern/importieren/laden.
- Script Studio: Ausführungsmodus, fünf Snippets, Tab-Einrückung, Ctrl+Enter zum Start, Ctrl+S zum Speichern, suchbare Funktionsreferenz mit Status und HTTPS-Textimport in den Editor.
- Playstyle-Editor und Runtime: Prioritäten, Runden, benannte Karten, Typfilter, Enchants, self/enemy/boss/ally und Mehrfachziele, Gesundheits-/Mana-/Effektbedingungen, draw und willcast. Inline-loadplaystyle, togglecombat und Auto-Combat arbeiten mit dem Bot.
- Grenzen: buypotions derzeit nur Commons/Hilda. Autopet, Deck-Presets, Welt-Navigator, Drop-Tracking und neue gambit/clear/echo/swap/req_met-Kartenfilter bleiben offen und werden nicht als umgesetzt ausgegeben.
- Maximal 64 KB Bot, 10.000 kompilierte Anweisungen, 128 Stackeinträge. Expertmode-Laufzeit nutzt das eingestellte Automatik-Zeitlimit; der Basis-Runner und Demo bleiben verfügbar.

## 0.1.1 Beta 8 · Dashboard und Freecam-TP

- Rechtsklick auf „Dashboard öffnen“ im Widget kopiert den aktiven Pairing-Code als Unicode in die Zwischenablage. Der Code wird nicht in Diagnose-Logs geschrieben.
- Bereits gekoppelte Dashboards werden erneut angesprochen, ohne einen neuen Tab zu öffnen. Windows versucht, das Dashboard-Browserfenster in den Vordergrund zu bringen.
- Ein neuer Kopplungsaufruf übergibt den Code per BroadcastChannel an einen bestehenden Tab derselben Origin und desselben Browserprofils. Der kurze Übergabe-Tab schließt sich, soweit der Browser dies erlaubt; sonst kann er manuell geschlossen werden. Ohne passenden Tab bleibt der neue Tab aktiv. Private und lokale Oberfläche sind getrennte Origins.
- Pairing-Code bleibt im Sitzungsspeicher des Tabs für Neuladen verfügbar; manuelles Trennen entfernt ihn.
- Freecam-TP gibt den von WizWalker angehaltenen Bewegungsupdate kurz frei, wartet auf die Spielerposition und stellt den Freecam-Patch auch nach Fehler/Abbruch wieder her. Die Kamera bleibt aktiv. Keine Erfolgsmeldung ohne Positionsprüfung.

## 0.1.1 Beta 7 · Diagnose und Kopplung

- Behebt fehlende Script-Tags für Bot-Parser, Standardbibliothek und Botkatalog. Der Fehler konnte die App-Initialisierung vor der automatischen Kopplung abbrechen.
- UI-Tests laden jetzt die tatsächliche Script-Reihenfolge aus index.html. Die lokale Oberfläche liefert alle benötigten Dateien aus.
- Ausführliche lokale DEBUG-Logs: Start/Updates, Zertifikat, Browseröffnung, HTTP/WebSocket, Authentifizierung, Client-Fenster, Prozesszugriff, Hook-Validierung, Befehlsdauer, Statuswechsel und Aufräumen. Fehler mit vollständiger Fehlerspur.
- Windows-EXE: %LOCALAPPDATA%\MythicWalker\bridge.log, maximal vier Dateien mit je 2 MB. Python-Starter: bridge/logs/bridge.log. Pairing-Codes werden redigiert; keine Bot- oder Auth-Payloads im Trace.
- Bridge-Seite: Verbindung testen und Diagnose herunterladen. Ohne Kopplung enthält der Export Browser-Logs; mit Kopplung zusätzlich Ausschnitte der Bridge-Logs. Browser-Logs überstehen Neuladen innerhalb desselben Tabs und sind auf 1000 Einträge begrenzt.
- Widget und Webkopplung zeigen den genauen Release-Tag.

## 0.1.1 Beta 6 · Client-Erkennung

- Windows-Fenstersuche mit pointerbreiten HWNDs und korrekt dimensioniertem Klassenpuffer.
- Fehlgeschlagener Prozesszugriff blockiert spätere Suchläufe nicht mehr; andere Clients bleiben verfügbar.
- Ein Fehler bei der ersten Suche trennt das Dashboard nicht mehr. Zugriffsmeldungen und die Anzahl gefundener Clients erscheinen im Aktivitätsprotokoll.
- Das Öffnen des Browsers überschreibt keine bereits erfolgreiche Kopplung mit „Kopplung wartet“.
- CI prüft auch die echte Windows-Fenstersuche; Wizard101-DE-Livebetrieb muss auf dem Spielrechner verifiziert werden.

## 0.1.1 Beta 5 · Bot- und Blockbibliothek

- Minimales Control Center: Übersicht, Hooking, Tools, Skripte/Bot und Combat.
- Bridge-Setup, große EXE-Kachel, Befehle und Quellen befinden sich auf der Bridge-Seite.
- Echter Bot-Fork: https://github.com/xLordTime/bots. Elf Deimos-Originale plus Safe Mob Farm im Katalog; Aktualisierung aus dem Fork per Button.
- Vier Bots mit unterstützter Syntax sind startbar. Acht originale Expertmode-Bots benötigen zusätzliche Deimos-Befehle; der Katalog benennt die fehlende Syntax und erlaubt das Bearbeiten. Keine Behauptung vollständiger Deimos-Kompatibilität.
- Eigene Bots erstellen, importieren, speichern, exportieren und löschen.
- Neun Standardblöcke, eigene Blöcke, JSON-Import/Export und dauerhafte Speicherung in der Bridge. `call safe_mob_pull` benötigt keine lokale Blockdefinition.
- Laufzeit für block/call, if/else, while/until, loop, times und break. Große Schleifen werden nicht aufgefaltet; unbekannte und rekursive Blockaufrufe werden vor Start abgelehnt.
- Optionaler Auto-Combat während eines Bots; manuelles cast/pass ist dann ausgeschlossen. Stop beendet Bot und Kampfautomatik.
- Zusätzliche Skriptbefehle: closestmob, Zonenwechsel abwarten, Navmap, Freecam, Fenster/Laden abwarten und Kampfkarten.
- Grenze: 64 KB pro Bot, 2000 Anweisungen einschließlich Bibliothek, 15 Minuten pro Lauf. Windows-Spielbetrieb benötigt zusätzlich einen Live-Test; automatisierte Adaptertests ersetzen ihn nicht.

## 0.1.1 Beta 4 · Widget-Steuerung

- Minus-Schaltfläche versteckt das Widget im Windows-Infobereich.
- F10 blendet das Widget global aus/ein, auch ohne Hook oder Dashboard-Verbindung.
- Tray-Symbol zeigt das Widget wieder; Bridge und Hooks laufen beim Verstecken weiter.
- Neue Web-Settings: bearbeitbarer Shortcut, versteckt starten und immer im Vordergrund.
- Widget direkt im Dashboard anzeigen/verstecken. Bestehende Settings werden migriert.

## 0.1.1 Beta 3 · Maus- und Kamera-Fix

- Hooken aktiviert keinen dauerhaften Mouseless-Cursor-Hook mehr.
- Automatische Dialog-, Sigil-, Fenster- und Kampfklicks aktivieren den Cursor-Hook nur für die jeweilige Aktion.
- Der Cursor-Hook wird auch bei Fehlern und Abbruch freigegeben.
- Nach dem Update alte Bridge beenden, neu starten und Clients erneut hooken.

## 0.1.1 Beta 2 · Projekt-Icons

- Eigenes App-Icon: arkane Kompassrose mit M-Monogramm.
- Windows-EXE, Status-Widget, Browser-Favicon und Dashboard verwenden dieselbe Identität.
- Passende SVG-Symbole für Bewegung, Kampf, Questing, Dialoge, Sigil und Freecam.
- Enthält alle Funktionen und Einstellungen der Beta 1.

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
