## Sound-Zentrale · Beta 17

Der neue Tab **Sound** verwaltet kurze Effekte einzeln in lokalen KIWAD-Archiven. Die mitgelieferte Aufnahme „Schaden bekommen“ ist als WAV (16-Bit-PCM) und Ogg-Vorbis vorbereitet. Es gibt keine bestätigte automatische Zuordnung zum DE-Trefferlaut: Installation erkennen, Sound-Archiv auswählen, nach `hurt`, `pain`, `damage`, `hit` oder `grunt` suchen und das Original vorhören. Danach die Aufnahme oder eine eigene Datei zuweisen.

- **Anwenden:** alle Wizard101-Clients und den offiziellen Launcher schließen, Original wählen, Ersatz vorhören, Bestätigung setzen und anwenden. Danach das Spiel neu starten. Ein Hook ist dafür nicht nötig. Der Austausch betrifft alle Clients derselben Installation; eine Datei kann von mehreren Figuren verwendet werden.
- Unterstützt werden kurze WAV-/Vorbis-Effekte bis 15 Sekunden / 3 MB. WAV wird im Browser auf die ursprüngliche Kanalzahl und Abtastrate umgewandelt. Eigene Ogg-Ziele benötigen Vorbis; Opus/OGA nicht lediglich umbenennen. MP3 und unbekannte Archiv-/Audioformate werden nicht verändert.
- Vor der ersten Änderung wird das vollständige Archiv unter `%LOCALAPPDATA%\MythicWalker\sounds\backups` gesichert. Arbeitskopie und Prüfsummen werden vor dem atomaren Austausch geprüft. Ausreichend freier Platz für Sicherung und Arbeitskopie ist erforderlich. **Original wiederherstellen** setzt nur den ausgewählten Sound zurück; beim letzten Zurücksetzen wird das Archiv bytegenau wiederhergestellt.
- Sounddateien und Installationspfad werden über die gepaarte lokale Bridge bearbeitet. Es gibt keinen externen Upload-Endpunkt. Dateivorgänge laufen als Statusauftrag, verhindern parallele Änderungen und blockieren Starts über den integrierten Launcher bis zum Abschluss.
- Experimentell: Format und Rücksetzen sind mit Testarchiven geprüft. Der tatsächliche Trefferlaut und die Wiedergabe im aktuellen DE-Spiel sind ohne lokale Spielinstallation noch nicht bestätigt. Spielupdates können Änderungen überschreiben. Extern veränderte Archive werden gesperrt, damit eine alte Sicherung kein Update überschreibt.

## Questen & Launcher-Schalter · Beta 16

- **Einstellungen → Launcher aktivieren** ist standardmäßig aus, auch nach Migration von Beta 15. Mit Aktivierung erscheint Launcher wieder als erster Tab. Ausschalten sperrt lokale Sitzungen/Tickets und stoppt weitere Starts; bestehende Spiele und gespeicherte Konten bleiben erhalten. Kontodaten bleiben ausschließlich im lokalen Windows-Tresor.
- **Questen:** Client im eigenen Seitenbereich wählen, bei Bedarf hooken und im Spiel eine Quest verfolgen. Der Tracker liest die aktive Quest-ID, Teilziel-ID, Journal, Hauptquest-/Abgabestatus sowie lokale Questtexte. DE-Texte werden bevorzugt; andernfalls Englisch bzw. der Sprachschlüssel. Keine zusätzlichen Hooks, Speicher-Schreiboperationen oder automatischen Spielaktionen für den Tracker.
- Die markierte Quest folgt alle drei Sekunden dem Spiel. Gleiche Namen werden nicht geraten: Entscheidend sind Quest-ID und bei eigenen Plänen optional Teilziel-ID. Zonenwechsel, Unhook, Verbindungsverlust und Lesefehler entfernen die alte Markierung. Metadata-Lesefehler können auf IDs zurückfallen. Große Journale werden begrenzt; fehlende Questdetails werden ausdrücklich angezeigt.
- **Overlay öffnen:** separates Browserfenster, Live-Verbindung über das geöffnete Dashboard. Auch außerhalb des Quest-Tabs weiter aktiv, solange das Overlay offen ist. Kein Always-on-top-/exklusives Vollbild-Overlay; Browser-Hintergrunddrosselung kann Updates verzögern.
- Das **Live-Journal** enthält angenommene Quests, keine komplette Welt-Reihenfolge. **Mein Questplan** ergänzt eine eigene Reihenfolge: aktuelles Ziel hinzufügen, JSON bearbeiten/importieren/exportieren. Der Plan bleibt im lokalen Browser-Speicher. Format: `{"version":1,"name":"Mein Plan","quests":[{"id":"123","goal_id":"456","name":"Eigener Questname","world":"Welt","area":"Gebiet","note":"Hinweis"}]}`. IDs sind Beispiele und müssen durch echte Spiel-IDs ersetzt werden. `goal_id` ist optional; gleiche Quest-IDs mit unterschiedlichen Teilziel-IDs ermöglichen Rückkehrphasen. Keine automatische Annahme, dass vorige Quests abgeschlossen wurden.
- **Auto Quest (Plan):** lokale Vorbereitung von Client-/Gruppen-Scope, Dialog/Kampf, Zeitlimit und Pause bei unbekannten Schritten. Speichern startet keinen Bot. Die bestehende einfache F3-Automatik bleibt in Tools; eine vollständige Quest-Zustandsmaschine ist noch nicht implementiert.
- Gestaltungsidee: [SpiralTracker](https://spiraltracker.com/). Keine verifizierte Open-Source-Lizenz gefunden; eigenständige Umsetzung ohne übernommene Website-Dateien, Bilder oder vollständige Guides. Questdaten werden lokal aus dem Spiel gelesen und über die gepaarte Loopback-Verbindung im Browser angezeigt; keine Quest-Abfragen an SpiralTracker oder andere externe Datenbanken.

## Launcher · Beta 15

Der erste Tab **Launcher** integriert die Kernfunktionen von [Wiz Q Launcher](https://github.com/xLordTime/wiz-q-launcher): lokale Kontoverwaltung, Import bestehender Konten, Regions-/Installationsauswahl, Mehrfachstart und Auto-Login.

1. Neue Bridge-EXE starten und Dashboard verbinden.
2. **Launcher → Launcher verbinden**; lokalen Netzwerkzugriff erlauben. Falls die Einbettung blockiert wird, **Eigenes Fenster** nutzen. Alternativ **Launcher lokal öffnen** im Bridge-Widget.
3. In der lokalen Ansicht den Windows-Kontotresor entsperren. Installationen suchen oder deren Ordner oberhalb von `Bin` angeben und speichern.
4. Unter **Wiz Q übernehmen** bestehende Konten importieren (ggf. Masterpasswort eingeben), oder Konten hinzufügen.
5. Konten auswählen und starten. Auto-Login sendet die Eingaben einmalig an den neu gestarteten Prozess; Anmeldung im Spielfenster prüfen. Bei langsamen Starts Wartezeit erhöhen. Danach im Control Center Clients suchen und gezielt hooken.

### Lokale Daten und Sicherheitsgrenzen

- Profil immer `%LOCALAPPDATA%\WizQLauncher`; bestehender Ordner wird verwendet, andernfalls angelegt. Originaldateien `config.json` und `data/accounts.enc.json` werden nur gelesen.
- Eigener Kontotresor `data/mythic-accounts.dpapi`: alle Kontodaten mit Windows DPAPI für den aktuellen Benutzer verschlüsselt. Konfiguration `mythic-launcher.json` enthält nur lokale Installationspfade und die Login-Wartezeit. Keine parallelen Schreibzugriffe auf das Wiz-Q-Originalformat.
- Import unterstützt das Wiz-Q-Fernet/PBKDF2-Masterpasswortformat, lokal per DPAPI gespeicherte Schlüssel, den alten Platzhaltermodus und ältere Klartextlisten. Das Original wird nicht verändert oder automatisch sicherer gemacht. Import ist kein fortlaufender Abgleich.
- Kontoansicht ausschließlich von `https://localhost:18762` (Loopback). Die Online-Oberfläche enthält nur einen getrennten Frame und erhält keine Accountdaten. Eine strikte Content Security Policy erlaubt dieser lokalen Ansicht keine externen Skripte, Formulare oder Netzwerkziele.
- Einmaliges Öffnungsticket: 30 Sekunden gültig. Erst die lokale Ansicht kann es in einen Sitzungsschlüssel umtauschen. API nur per POST, exakte lokale Origin-/Host-Prüfung, kein CORS, keine Cookies, kein Browser-Speicher, keine Konto-/Passwort-Logs. Sitzung maximal 30 Minuten, widerrufen beim Bridge-Disconnect; Schließen der Ansicht meldet die Sitzung ab.
- Keine Discord-Präsenz, Webhooks, externes Fehlerreporting oder Cloud-Backups aus dem Launcher. Wizard101 selbst muss für die Anmeldung seinen Spielserver kontaktieren. Die lokale Kontoverwaltung führt keine eigene Online-Anmeldung durch.
- Konto-Aliasse und Benutzernamen werden nicht in Spiel-Fenstertitel geschrieben. Konten wählen und bearbeiten erfolgt ausschließlich in der lokalen Ansicht; allgemeine Bridge-Statusdaten bleiben separat.
- DPAPI schützt gespeicherte Dateien, nicht vor Schadsoftware mit denselben Windows-Benutzerrechten, kompromittierten lokalen Programmen oder berechtigten Browser-Erweiterungen. Kein Schutzversprechen für einen bereits kompromittierten Rechner. Auto-Updates verwenden weiterhin die bestehende GitHub-/Prüfsummenprüfung; eine unabhängige Update-Signatur ist noch nicht umgesetzt.
- Unterstützte Launcher-Regionen: DE/US/FR/IT/GB/PL/ES/GR. Memory-Hooks bleiben auf den gepinnten DE-WizWalker abgestimmt. Kein automatisches Hooken beim Login, keine Übernahme der Wiz-Q-Memory-Erweiterungen, kein erzwungenes Schließen laufender Spiele beim Stoppen.

# Mythic Walker · 0.1.1 Beta 10

## Script Studio und Deimos Expertmode (Beta 9)

Der Skriptbereich besitzt jetzt zwei Laufzeiten. **Deimos Expertmode** verwendet den originalen Deimos-Sprachkern (Tokenizer, Parser, Semantik und Compiler); eine eigene begrenzte Bridge-VM führt die Aktionen mit dem unveränderten DE-WizWalker aus. **Basis / Demo** bleibt für vorhandene einfache Skripte verfügbar. Automatisch wählt Expertmode für `##deimos_expertmode` oder typische Expertmode-Deklarationen. Live-Syntaxprüfung benötigt Beta 9.

Alle zwölf mitgelieferten Katalogdateien lassen sich übersetzen; die Bridge prüft vor dem Start erneut. Das bestätigt Sprache und verfügbare Adapter, nicht den vollständigen Live-Ablauf jedes Community-Bots. Original-Kommentare, Startzone, Clientzahl, Decks und nötige Vorbereitungen beachten.

```text
##deimos_expertmode
con count = 0
settimer farming
times 10 {
    call safe_mob_pull
    call after_combat
    addone count
}
log $count
endtimer farming
```

Unterstützt werden Blockaufrufe mit transitiver Standardbibliothek, return/break, if/elif/else, logische Operatoren, Zahlen/Prozentvergleiche, Variablen/Zähler, Timer, Bereiche (`p1:p3`), `except`, `any`/`sameany`, `&&`, Bedingungen für Stats, Fenster, Kampf, Zone, Quests und Positionen. Wiki-Varianten wie `loop 5 times`, Timer und `setyaw` werden an den Sprachkern angepasst. Maximal 64 KB, 10.000 IR-Anweisungen und 128 Stackeinträge; das Expertmode-Zeitlimit folgt dem Automatik-Zeitlimit in Settings.

Neue Live-Aktionen umfassen relative/clientbasierte Teleports, Navmap-Koordinaten, Laufen mit freigegebenen Tastendrücken, UI-Klicks über vollständige Pfade, virtuellen Cursor, Warten auf Kampf/Dialog/Frei/Zone/Fenster, Tränke, Freundeslisten und Relog. `buypotions` unterstützt aktuell Hilda im Commons; die automatische Weltreise ist noch nicht vorhanden.

Der Playstyle-Editor prüft Regeln und lädt sie für ausgewählte Clients. Im Bot funktioniert ein mehrzeiliges `loadplaystyle` gefolgt von `togglecombat on`; alternativ Auto-Combat beim Start auswählen. Prioritäten `|`, Rundenvorgaben `{1}`, Enchants `[Epic]`, Typfilter, Ziele self/enemy/boss/ally/Mehrfachziele und Bedingungen wie `?(self.health < 30%)` sind umgesetzt. Inline-Playstyles werden nach dem Bot wieder durch den vorherigen Stand ersetzt. Enchants sind optional, sofern keine passende Karte vorhanden ist.

**Noch offen:** Pet-Tanz, Deck-Presets, weltübergreifendes `tozone`, Drop-Tracking und moderne gambit/clear/echo/swap/req_met-Filter. Nicht verfügbare Befehle werden klar abgelehnt; UI- und Questpfade benötigen zusätzlich Prüfung im aktuellen DE-Spiel. Quellen: https://github.com/Deimos-Wizard101/Deimos-Wizard101/wiki, Upstream d7ef56eb51c5b5316cadba40ca554ec442a5dcee.

## Dashboard und Freecam (Beta 8)

**Rechtsklick auf Dashboard öffnen** kopiert den aktuellen Code zum manuellen Einfügen unter Bridge. Linksklick verwendet eine bestehende Kopplung. Bei neuen Kopplungen koordiniert die Webseite bestehende Tabs per BroadcastChannel: gleicher Browser, gleiches Profil, gleiche Origin. Der Übergabe-Tab schließt automatisch, soweit vom Browser erlaubt. Windows/Browser können den Fokuswechsel beschränken; in diesem Fall den vorhandenen Tab selbst auswählen. Ohne passenden Tab startet ein neues Dashboard. Ein bereits gekoppelter Tab hält seinen Code in sessionStorage bis zum Schließen/manuellen Trennen; Neuladen kann dadurch automatisch erneut koppeln. Bridge-Neustart erzeugt weiterhin einen neuen Code.

Freecam-TP hebt die Bewegungs-Pause für den Teleport kurz auf und setzt sie anschließend wieder. Der Befehl prüft die erreichte Spielerposition (25 Einheiten Toleranz, 3 Sekunden), statt nur den Aufruf zu bestätigen. Der aktuelle DE-Livebetrieb benötigt zusätzlich einen Test im Spiel.

## Diagnose (Beta 7)

Behebt einen Initialisierungsfehler durch fehlende Script-Tags, der die automatische Kopplung verhindern konnte. Tests verwenden jetzt die reale HTML-Ladefolge. Unter **Bridge → Verbindung testen / Diagnose herunterladen** stehen Browser-Logs auch ohne Kopplung zur Verfügung. Bei erfolgreicher Kopplung enthält `MythicWalker-Diagnose.json` zusätzlich native Logs.

EXE: `%LOCALAPPDATA%\MythicWalker\bridge.log`; Python-Starter: `bridge/logs/bridge.log`. Rotation: 2 MB, drei Backups. Logs enthalten Zeit, Thread, Release, Startschritte, Netzwerkereignisse, Client-PIDs, Hook-Phasen, Befehle ohne Payload, Laufzeiten und Fehlerspuren. Pairing-Codes werden redigiert. Browser-Logs sind auf 1000 Einträge begrenzt und bleiben im selben Tab über Neuladen erhalten. Diagnoseexport erfolgt nur auf Klick; es wird nichts automatisch hochgeladen.

## Client-Erkennung (Beta 6)

Pointerbreite Windows-Fenstersuche; fehlgeschlagener Prozesszugriff wird bei der nächsten Suche erneut versucht. Startfehler bei der Erkennung trennen die Webkopplung nicht mehr. Unter Hooking → Clients suchen erscheint die Zahl gefundener Spielclients im Aktivitätsprotokoll. Bei Zugriff verweigert Bridge und Spiel mit denselben Windows-Rechten starten.

## Bot- und Standardbibliothek (Beta 5)

Bot-Fork: https://github.com/xLordTime/bots. Enthält unveränderte Deimos-Originale, `default_lib/`, eine importierbare `default-library.json` und Safe Mob Farm. Der Webkatalog startet mit zwölf Dateien (elf Originale plus ein MythicWalker-Beispiel). **Vom Fork aktualisieren** liest den aktuellen Commit, dann alle `.txt`-Bots unter `bots/`. Eigene Dateien mit Metadaten `@name`, `@author`, `@zone` und `@clients` erscheinen nach der Aktualisierung. `@zone: *` erlaubt beliebige Startzonen. Lokale Bots lassen sich ebenfalls importieren, im Browser speichern, exportieren und löschen.

**Aktuell startbar:** Foulgaze, PublishTest1, Harvest Lord Test und Safe Mob Farm. Die acht komplexeren Originaldateien sind im Editor verfügbar, benötigen aber weitere Expertmode-Befehle (z. B. Variablen, Pfadbedingungen, Playstyles oder Tränke). Der Katalog zeigt die erste nicht unterstützte Anweisung und deaktiviert den direkten Start. Die Bridge validiert erneut und führt unbekannte Syntax nicht aus. Clientzahl und Original-Startzone werden beim Katalogstart geprüft; englische interne Namen und die Startbedingungen des Autors vor dem Live-Lauf beachten.

Unter **Standardbibliothek · Blöcke** stehen `safe_mob_pull`, `wait_combat_done`, `interact_all`, `quest_nav`, `wait_loading`, `step_forward`, `restore_speed`, `sigil_enter` und `after_combat`. Eigene Blöcke können als Inhalt oder als vollständige `block name { … }`-Definition gespeichert werden. **Call einfügen** setzt den Aufruf an die Cursorposition. JSON-Import/Export sichert eigene Blöcke. **In Bridge speichern** persistiert sie als `user-blocks.json`, **Aus Bridge laden** übernimmt diese in den Browser. Start und Prüfung übertragen die aktuelle Browserbibliothek automatisch. Für Spiel-Shortcuts Änderungen zuvor in der Bridge speichern. Inline-Definitionen im Bot überschreiben Bibliotheksblöcke; entfernte eigene Überschreibungen stellen den Standard wieder her.

```text
##deimos_expertmode
times 999999 {
    call safe_mob_pull
    call after_combat
}
```

`block`, `call`, `if/else`, `while`, `until`, `loop`, `times` (1–999999) und `break`/`exitloop` werden zur Laufzeit interpretiert. Unterstützte Bedingungen: `incombat`, `loading`, optional `not` und `any`/`mass`/`p1` etc. Befehle ohne Clientpräfix richten sich an die Auswahl. Grenzen: 64 KB Bot, 16 KB pro Bibliotheksblock, 90 eigene Blöcke / 256 KB Bibliothek, 12 verschachtelte Ebenen, 16 Blockaufrufe, 2000 Anweisungen einschließlich Bibliothek und 15 Minuten Laufzeit. Schleifen bleiben kompakt; unbekannte oder zyklische Aufrufe sind Fehler. Stop bleibt auch in Schleifen ohne Pause wirksam.

`tp closestmob` verwendet den schreibgeschützten NPCBehavior-Aggro-Flag entsprechend Deimos SprintyClient und teleportiert zum nächstgelegenen feindlichen Actor. Keine Entities gefunden bedeutet Abbruch. Das ist ein eigener Laufzeitpfad und muss zusätzlich im aktuellen DE-Spiel bestätigt werden. `waitforzonechange completion` merkt sich die zuletzt bestätigte Zone, sodass ein Übergang vor Erreichen der Warteanweisung erkannt wird. Zonen- und Ladewartezeit sind auf 120 Sekunden begrenzt, Kampfwartezeit auf 300 Sekunden.

Die Editor-Option **Auto-Combat während dieses Bots** nutzt die Regeln aus Combat. Andere Automatikmodi werden beim Start beendet; die Kampfautomatik endet zusammen mit dem Bot. `cast`/`pass` im selben Bot ist mit dieser Option nicht erlaubt. Ansonsten Kampf manuell steuern. Alle Module und die lokale Bridge bleiben für Browser-Skripte notwendig.

## Aktuelle GitHub-Beta

Repository: https://github.com/xLordTime/MythicWalker
Release: `v0.1.1-beta.14` (Prerelease), App-Version `0.1.1`, Kanal `beta`.
Die älteren Abschnitte unten dokumentieren die bisherigen Entwicklungsstände;
für die aktuelle EXE und Belegung gilt dieser Abschnitt.

Die Windows-EXE wird mit GitHub Actions gebaut, im Release als `MythicWalker.exe`
veröffentlicht und mit einem SHA-256-Manifest versehen. Die Beta-App prüft auch
neuere Vorabversionen. Zukünftige Betas benötigen einen erhöhten `RELEASE_TAG`
(z. B. `v0.1.1-beta.2`) in `bridge/version.py`.

| Taste | Funktion |
|---|---|
| X | X an alle gehookten Clients |
| F8 | XYZ zum aktiven Client / Leader synchronisieren |
| F7 | Navmap Quest-TP für aktiven Client |
| F6 | Navmap Quest-TP für alle |
| F5 | Speed ein/aus |
| 9 | Auto-Combat ein/aus |
| F4 | Auto-Dialog ein/aus |
| F3 | Auto-Questing ein/aus |
| F2 | Auto-Sigil ein/aus |
| F1 | Freecam |
| Shift+F1 | Charakter zur Freecam |
| Ctrl+Alt+F8 | Alle Automatiken und Skript stoppen |

Native Tasten greifen ausschließlich bei fokussiertem, gehooktem Wizard101.
Im Browser gelten Shortcuts außerhalb von Eingabefeldern und Dialogen. Der fokussierte
Wizard ist der aktive Client; im Browser kann ein Leader unter Movement gewählt werden.
„Alle“ umfasst gehookte Clients, maximal 16. Unter Settings ist der Scope auf Auswahl
änderbar. Gleichzonige Clients folgen standardmäßig dem Leader-Quest-Ziel, andere ihrem
eigenen Ziel; auch dieses Verhalten ist editierbar.

Automatiken verwenden die beim Start gültigen Clients. Questing und Sigil schließen
sich aus; Combat und Dialog können parallel laufen. Start eines Skripts, Unhooken,
Trennen oder Beenden stoppt alle Automatiken. Die konfigurierbare Laufzeit ist 1–60 Minuten.
Kampfregeln sind eine Prioritätenliste: `LifeBlade@self`, `any<aoe>@enemy`, `pass`.
Eine Auswahl pro Client und Runde verhindert wiederholte Klicks. Questing navigiert
zum aktuellen Ziel, interagiert mit X und bedient Dialoge. Sigil merkt sich den Startpunkt
und kann nach Rückkehr erneut beitreten. Vor Start alle Clients am Sigil positionieren.
Komplexe Weltübergänge und Dungeon-Ausgänge können manuelle Schritte benötigen.
Details und Grenzen: RELEASE_NOTES.md. Vorherige Browser-Settings werden migriert.


Ein eigener Wizard101-DE-Client mit moderner Weboberfläche und lokaler Windows-Bridge.

Dashboard: https://mythic-walker.lord-time.chatgpt.site

## Architektur und tatsächlicher Umfang

Die gehostete Oberfläche läuft online. WizWalker und die Memory-Hooks laufen **auf demselben Windows-PC wie Wizard101**. Ein normaler Browser und ein Cloud-Server können den Prozessspeicher deines PCs nicht direkt öffnen. Deshalb ist eine lokale Bridge zwingend nötig. Nach der einmaligen Einrichtung werden die implementierten Spielaktionen über die Weboberfläche bedient.

`HTTPS-Dashboard → WSS localhost:18761 → Python-Bridge → WizWalker → lokaler Spielprozess`

Die Verbindung bindet nur `127.0.0.1`; sie ist kein Fernzugriff über das Internet oder von einem Smartphone. Kein Port-Forwarding. Standardmäßig ist nur die oben genannte Site-Origin und die lokale Oberfläche erlaubt. Der bei jedem Start zufällig erzeugte Pairing-Code wird nicht im Browser gespeichert.

**Implementiert:**

- Client-Erkennung und Auswahl mehrerer Prozesse.
- Hook/Unhook über WizWalker, Timeout und Aufräumen bei Fehlern.
- Live-Daten: Position, Zone, HP, Mana, Level und Kampfstatus.
- XYZ-Teleport, Positions-Sync innerhalb derselben Zone und eindeutiger Entity-Teleport.
- Tasteneingaben, Freecam-Umschaltung und Kamerarücksetzung vor Unhook.
- Entity-Liste, UI-Fensterbaum, Klick auf ein eindeutiges sichtbares Fenster.
- Kampfkarten auslesen und manuell spielen: ohne Ziel/AoE, selbst oder erster lebender Gegner. Die Bridge prüft die Planungsphase.
- Validierter Skript-Runner mit Fortschritt und Stop; siehe Syntax unten.
- Browserlokale Skriptbibliothek und Wegpunkte, Skript- und Log-Export.
- Expliziter Demo-Modus ohne Spielzugriff, responsive Oberfläche und reduzierte Animationen nach Systempräferenz.

**Noch nicht integriert:** vollständiger Deimos-Parser, Blocks/Loops/closestmob, FriendTP, Playstyles, Auto-Quest, Auto-Combat, Fishing, Pet-Training und vollständige Raid-Module. Die Modul-Seite bezeichnet diese als spätere Erweiterungen. Andere Projekte sind Quellen und mögliche Adaptervorlagen, keine eingebauten Funktionen.

## Windows: starten

Voraussetzung: Windows 64-bit, Python 3.11–3.13 (64-bit, `py` verfügbar), Internet für die erste Installation und Wizard101 DE. Die Live-Bridge ist hier noch nicht gegen einen realen Windows-Spielprozess geprüft.

1. `MythicWalker_Starter.zip` entpacken.
2. PowerShell im entpackten Verzeichnis öffnen:

```powershell
powershell -ExecutionPolicy Bypass -File .\bridge\Setup.ps1
powershell -ExecutionPolicy Bypass -File .\bridge\Trust-Local-Bridge.ps1
```

`Setup.ps1` sucht gezielt CPython 3.13, 3.12 oder 3.11 (64-bit, Standard-Build). Python 3.14 wird für die Bridge nicht verwendet. Eine bereits angelegte unpassende `.venv` wird vor dem Neuerstellen unter `.venv-before-fix-…` gesichert. Anschließend installiert das Setup die Abhängigkeiten, prüft sie mit `pip check` und erzeugt ein lokales Zertifikat. Für `regex` werden ausschließlich fertige Wheels verwendet. `Trust-Local-Bridge.ps1` erklärt den Eintrag und fragt ausdrücklich nach `JA`, bevor **dieses lokale Zertifikat** in den Windows-Benutzer-Zertifikatsspeicher übernommen wird. Für die HTTPS-Webseite ist eine vertrauenswürdige WSS-Verbindung nötig. Administratorrechte sind für den Zertifikatseintrag in CurrentUser nicht vorgesehen.

3. `bridge\Start-Bridge.cmd` starten.
4. Wizard101 öffnen und mit deinem Charakter in der Welt einloggen.
5. Dashboard öffnen → **Bridge einrichten** → Pairing-Code aus dem Bridge-Fenster eingeben → **Verbindung herstellen**.
6. **Übersicht → Clients suchen → auswählen → Hooken**.

Die Bridge braucht ausreichend Windows-Prozessrechte. Läuft das Spiel erhöht, kann der Zugriff aus einem normalen Bridge-Prozess scheitern. Fehler werden angezeigt; Zugriffs- oder Pattern-Probleme werden nicht als erfolgreicher Hook ausgegeben.

### Setup schlägt mit regex / C++-Build-Tools fehl

Der ursprüngliche Installer konnte über `py -3` versehentlich Python 3.14 verwenden. Das korrigierte Setup wählt eine passende Version explizit aus. Installiere bei Bedarf Python 3.13 (64-bit, Standard-Build) zusätzlich, entpacke das aktualisierte Starterpaket und führe Setup erneut aus. Python 3.14 muss nicht deinstalliert werden. Die Trust-Skripte erst nach erfolgreichem Setup ausführen. Die PowerShell-Dateien sind jetzt als UTF-8 mit BOM gespeichert, damit Windows PowerShell 5.1 deutsche Zeichen richtig anzeigt.

### Windows-Fehler WinError 10054 / Proactor

Version 0.1.1 startet die lokale HTTPS/WSS-Bridge unter Windows explizit mit `SelectorEventLoop`. Damit wird der im ursprünglichen Log fehlschlagende Proactor-Aufräumcallback umgangen. Die Bridge benötigt keine asynchronen Windows-Pipes oder Subprocess-Transports. Andere Verbindungsfehler werden weiter angezeigt. Ein Browser kann die Verbindung weiterhin bei Zertifikats-, Berechtigungs- oder Pairing-Problemen ablehnen; die Ursache eines Reset ist durch den Traceback allein nicht bekannt. Nach erfolgreichem Pairing erscheint jetzt auch im Bridge-Fenster `Dashboard gekoppelt (LIVE).`.

### Falls die Verbindung nicht klappt

- Prüfe, dass das Bridge-Fenster offen ist.
- Öffne https://localhost:18761/health. Bei Zertifikatsfehlern Vertrauen einrichten und Browser neu starten.
- Falls Chrome/Edge nach lokalem Netzwerkzugriff fragt, erlaube ihn für diese Site.
- Die identische Oberfläche steht auch unter https://localhost:18761 bereit. Damit entfällt der Zugriff von einer gehosteten Origin auf localhost. Die Bridge und das Zertifikat bleiben erforderlich.
- Pro Bridge ist nur eine authentifizierte Dashboard-Sitzung möglich. Alte Sitzung trennen.
- Der Code ändert sich bei jedem Bridge-Start. Er wird nur im initialen WebSocket-Handshake gesendet.

Beim Trennen werden laufende Skripte gestoppt und Hooks entfernt. Beim Stoppen wird ein bereits laufender Memory-/Tastenschritt zunächst zu Ende geführt, damit Key-up und Patch-Abschluss nicht mitten im Schritt abgeschnitten werden. Warte maximal bis zum Schritt-Timeout (25 Sekunden). Beim normalen Beenden der Bridge mit Strg+C wird ebenfalls aufgeräumt. Erzwungenes Prozessbeenden kann dieses Aufräumen verhindern.

Vertrauen entfernen:

```powershell
powershell -ExecutionPolicy Bypass -File .\bridge\Remove-Local-Trust.ps1
```

### Eigene Windows-EXE bauen

```powershell
powershell -ExecutionPolicy Bypass -File .\bridge\Build-EXE.ps1
```

Das erzeugt `bridge\dist\MythicWalker.exe`. Ein ausgeführter Windows-Build steht noch aus. Die Desktop-App erzeugt und vertraut ihr lokales Zertifikat beim ersten Start für den aktuellen Benutzer automatisch. Weitere Informationen unter „Version 0.3.0“. Zertifikate und private Schlüssel gehören nicht in Release-Pakete.

## Skripte: unterstützter Teil der Deimos-Syntax

```text
# p1/p2 sind die Reihenfolge der ausgewählten Clients in der Oberfläche.
# completion wartet auf das Ende bereits laufender Kämpfe.
mass waitforcombat completion
sleep 0.5
mass sendkey W 0.2
sleep 3
p1 tp XYZ(100, 200, 0)
```

Unterstützt: `sleep`, `mass` bzw. `p1/p2/…`, `sendkey`, `tp XYZ(...)`, `waitforcombat completion`.
Grenzen: 200 Schritte, 16 KB Quelltext, Schlafen pro Schritt max. 60 Sekunden, Tastendauer 0.01–5 Sekunden, Kampfwartezeit max. 5 Minuten. Neue Schritte starten nicht mehr nach 15 Minuten Gesamtlaufzeit; die Prüfung erfolgt an Schrittgrenzen. Unbekannte Syntax wird vor Start zurückgewiesen. Es gibt kein `eval`, keine Python-Ausführung, keine freien Memory-Adressen und keinen Shell-Endpunkt.

Der Runner ist ein eigener kleiner Parser, **kein vollständiger Deimos-Ersatz**. Ein Syntax-Check kann nicht garantieren, dass ein Spielzustand oder ein Ziel zur Laufzeit verfügbar ist. Mehrclient-Aktionen laufen nacheinander; bei einem Fehler können vorherige Clients bereits bearbeitet sein.

Skripte und Wegpunkte werden pro Browser-Origin gespeichert, nicht serverseitig synchronisiert. Die Online- und lokale Oberfläche haben daher getrennte Browserdaten. Protokolle und Skripte lassen sich exportieren; Pairing-Codes werden nicht protokolliert.

## Backend & untersuchte Quellen

DE-Backend: [Vindaloniak/wizwalker](https://github.com/Vindaloniak/wizwalker), Branch `development`, Commit **13223e0911578e586975ace496d9f586ac4538da**, Commitdatum **14.09.2026**. Die Abhängigkeit ist auf diesen Commit fixiert; sie wird nicht bei jedem Start automatisch aktualisiert. Repo-Stand am 11.10.2026 abgefragt. „Aktueller GitHub-Stand“ bedeutet nicht, dass die Offsets mit jedem Spiel-Patch funktionieren.

[Deimos-Wizard101/wizwalker](https://github.com/Deimos-Wizard101/wizwalker) wurde als Upstream geprüft. Die Bridge nutzt die vorhandenen Client-/Hook-/Memory-Objekt-APIs, statt Offsets in JavaScript zu duplizieren.

Weitere gelesene READMEs:

- [Slackaduts/Deimos-Wizard101](https://github.com/Slackaduts/Deimos-Wizard101): verweist auf die neue Deimos-Organisation.
- [CIick/FishyBusiness](https://github.com/CIick/FishyBusiness): konfigurierbares Fishing auf WizWalker.
- [Lxghtend/raid-utility-tools](https://github.com/Lxghtend/raid-utility-tools): Raid-Hilfen, Hook-Verwaltung, Clientdaten und Teleports.
- [StarrFox/wizdancer](https://github.com/StarrFox/wizdancer): Dance-/Pet-Training.
- [LaurenzLikeThat/wiztype](https://github.com/LaurenzLikeThat/wiztype): Type-Dumps und Offset-Diagnose.
- [Slackaduts/wizdiff](https://github.com/Slackaduts/wizdiff): Spielversions-Vergleiche.
- [vbe0201/wizproxy](https://github.com/vbe0201/wizproxy): separates Packet-Proxy-Projekt, keine Integration in diese Bridge.

Die im Suchlauf gefundenen Forks von nboj, notfaj und 7e11 sind in `sources.json` verlinkt. Deren vollständiger Quellcode wurde nicht umfassend geprüft. In dieser Version ist nur WizWalker eine eingebundene Spielbibliothek.

## Entwicklerstruktur

- `dist/`: buildlose Online-Oberfläche.
- `bridge/server.py`: TLS, Pairing, Protokoll, Runner und Sitzungslebenszyklus.
- `bridge/adapter.py`: realer WizWalker-Adapter und eigenständiger Demo-Adapter.
- `bridge/protocol.py`: Validierung und Skriptparser ohne Spielabhängigkeit.
- `bridge/web/`: Kopie der Oberfläche für den Starter und EXE-Build.
- `tests/`: Bridge- und Protokollprüfungen.

Live-Origin ändern: `server.py --origin https://deine-domain.example` (kein abschließender Slash). Standard bleibt die hier veröffentlichte Site.

## Verifikation

```text
python -m unittest discover -s tests -v
node tests/test_frontend.cjs
node --check dist/app.js
```

Geprüft: echte TLS-WebSocket-Verbindungen mit Demo-Adapter, Origin- und Token-Abweisung, Einzelsitzung, Hook-Failure-Aufräumen mit einem Mock-Client, Skriptvalidierung, Stop, Ende laufender Schritte, Disconnect-Unhook, private Dateiabschirmung, lokale Assets und Zertifikatsvalidierung; JavaScript-Parser, HTML-Escaping und DOM-ID-Verträge.

Nicht geprüft: echter Wizard101-DE-Prozess unter Windows, Spielfunktionen im Livebetrieb, Windows-EXE-Build und gerenderte Browserdarstellung. Diese Einschränkungen gelten auch für die als „implementiert“ bezeichneten Live-Adapter.

## Lizenz

GPL-3.0-or-later. Siehe `LICENSE` und `THIRD_PARTY_NOTICES.md`. WizWalker wird als Abhängigkeit installiert; sein Quellcode ist unter dem fixierten Commit verfügbar. Das Starterpaket enthält den vollständigen Quellcode dieses Grundgerüsts.

## Version 0.2.0: Shortcuts und Einstellungen

Im Dashboard unter **Einstellungen** kannst du Shortcuts frei eingeben oder aufnehmen,
Tastendauer (0,01–5 Sekunden) und Status-Intervall (0,5–10 Sekunden) bearbeiten.
Ein leeres Shortcut-Feld deaktiviert die Aktion. Doppelte Kombinationen werden abgelehnt.
Anzeigeoptionen: drei Akzentfarben, kompakte Darstellung, reduzierte Animationen,
Erfolgs-Benachrichtigungen und 50–1000 Protokoll-Einträge. Import/Export ist als JSON möglich.
Änderungen mit **Änderungen speichern** übernehmen. Der Browser behält die Einstellungen
und überträgt seine Steuerungskonfiguration bei jeder Kopplung an die Bridge.
Die Bridge speichert diese in `bridge/user-settings.json` (bei EXE neben der EXE).
Pairing-Code, Client-Auswahl und Skript-Inhalt werden dort nicht gespeichert.

| Standard-Shortcut | Aktion |
|---|---|
| Ctrl+Alt+F2 | Clients suchen |
| Ctrl+Alt+F3 | Auswahl hooken |
| Ctrl+Alt+F4 | Auswahl unhooken |
| Ctrl+Alt+F5 | Position zum ersten ausgewählten Client synchronisieren |
| Ctrl+Alt+F6 | Freecam umschalten |
| Ctrl+Alt+F7 | Aktuellen Skript-Editor starten |
| Ctrl+Alt+F8 | Skript stoppen |
| Ctrl+Alt+F9 | X senden |
| Ctrl+Alt+F10 | W senden |

Im Browser sind die Shortcuts sofort verfügbar (außer beim Bearbeiten von Eingabefeldern
und in geöffneten Dialogen). **Shortcuts auch im Spiel** aktiviert Windows-RegisterHotKey:
Die Kombinationen funktionieren systemweit, während das Dashboard gekoppelt ist, auch
bei fokussiertem Wizard101. Sie verwenden die im Dashboard ausgewählten Clients.
Das Skript verwendet den aktuellen Editor-Inhalt, einschließlich ungespeicherter Änderungen.
Belegte Tastenkombinationen erscheinen im Shortcut-Status; im fokussierten Dashboard gibt
es dafür einen Browser-Fallback. Beim Aufnehmen werden globale Shortcuts kurz pausiert.
Beim Trennen werden sie abgemeldet. F12 und die Windows-Taste sind nicht verfügbar.

**Update einer bestehenden Installation:** Bridge stoppen, `MythicWalker_Shortcuts_Update.zip`
in den bisherigen Starter-Ordner entpacken und Dateien überschreiben. `.venv`, Zertifikate
und vorhandene lokale Einstellungen bleiben erhalten. `bridge\Start-Bridge.cmd` erneut
starten und Dashboard mit Strg+F5 neu laden. Keine erneute Installation nötig.

## Version 0.3.0: Desktop-App und Werkzeuge

### Desktop starten

Die EXE heißt **MythicWalker.exe**. Sie enthält Python und die Bridge; auf dem Ziel-PC ist
keine Python-Installation erforderlich. Die Weboberfläche wird im Standardbrowser geöffnet.
Das kleine native Win32-Fenster rechts unten zeigt Update, Zertifikat, Bridge, Browser,
Kopplung und Client-/Hook-Status. Es enthält nur „Dashboard öffnen“ und „Beenden“.
Beenden stoppt Automatik und entfernt Hooks. Alle Spielaktionen und Settings bleiben im Web.
Die App benötigt keine Qt-/Electron-/WebView-Laufzeit.

Beim ersten Start wird das lokale TLS-Zertifikat im Zertifikatsspeicher **des aktuellen
Windows-Benutzers** registriert. Chrome/Edge können zusätzlich nach lokalem Netzwerkzugriff
fragen. Bei der privaten Website kann einmalig die ChatGPT-Anmeldung nötig sein.
Die App meldet dich nicht an einem fremden Konto an: Sie koppelt ihre lokale Bridge.
Der Pairing-Code wird als URL-Fragment übergeben, unmittelbar aus der Adresszeile entfernt
und nicht in Browser-Speicher oder App-Konfiguration gespeichert. „Dashboard öffnen“ koppelt
nach einer Trennung erneut. Bereits laufende Bridges müssen vorher beendet werden.

App-Daten liegen unter `%LOCALAPPDATA%\MythicWalker`: Zertifikate, Settings, Update-Versionen
und bei einem Startfehler `bridge.log`. Bei der ersten EXE-Nutzung kannst du
`bridge/user-settings.json` aus der bisherigen Installation in diesen Ordner kopieren.
Der Browser überträgt seine Settings weiterhin beim Koppeln.

**Aus Quellcode testen:** Nach dem vorhandenen Setup `bridge/Start-Desktop.cmd` starten.
**Lokal auf Windows bauen:** `bridge/Build-EXE.ps1` ausführen. Ergebnis:
`bridge/dist/MythicWalker.exe` plus `bridge-release.json`.

### GitHub-Builds und Updates

Der Workflow `.github/workflows/windows-release.yml` baut mit Windows und Python 3.13,
führt Tests aus und stellt EXE und SHA-256-Manifest als Actions-Artefakt bereit.
Manuell über **Actions → Windows Bridge Release → Run workflow** mit aktivem Publish-Schalter
wird daraus Release `v0.3.0`. Auch ein Push der Bridge-Dateien auf `main` startet Build und Release automatisch; vorhandene Releases bleiben unverändert. Später lösen auch Tags `vX.Y.Z` einen Release aus. Version in
`bridge/version.py` vorher erhöhen. Releases sind unveränderlich: Eine vorhandene Version
nicht nochmals veröffentlichen, sondern eine neue Versionsnummer verwenden.

Der Workflow hinterlegt automatisch sein eigenes Repository als Updatequelle.
Für einen lokalen Build kann `bridge/release_source.json` zuvor so befüllt werden:
`{"repository":"DEIN_ACCOUNT/DEIN_REPOSITORY"}`.
Die fertig gebaute App prüft beim Start **öffentliche GitHub-Releases** ohne eingebetteten Token.
Neuere stabile Versionen werden heruntergeladen, per SHA-256 gegen das Release-Manifest
geprüft, in einem Versionsordner installiert und gestartet. Die ursprüngliche EXE bleibt
unverändert und kann bei Netzwerkproblemen weiterlaufen. Updates erfolgen vor dem Hooken.
Die Prüfsumme erkennt beschädigte Downloads; sie ersetzt keine Herausgebersignatur.

**Historischer Stand vor GitHub-Anbindung:** Ein neues GitHub-Repository wurde noch nicht angegeben.
Deshalb liegen Workflow und EXE-Quellen bereit, aber noch kein ausgeführter Windows-Build
oder aktiver GitHub-Release vor. Ein öffentliches Repository mit diesen Dateien ist die
vorgesehene Releasequelle; private Releases benötigen zusätzliche GitHub-Authentifizierung.

### Zusätzliche Webfunktionen

Unter **Werkzeuge**: Quest-Ziel lesen und direkter Quest-Teleport; nächstgelegene Entity
nach Namen; Geschwindigkeit 0–300 % mit Wiederherstellung des ursprünglichen Werts;
Teleport zur Freecam; Fenstertitel ändern; Dialog-„Weiter“-Automatik (max. 15 Minuten,
pausiert im Kampf/beim Laden); Charakter-Statistiken auslesen. Keine vollständige
Deimos-Autoquesting-/Navmap- oder Auto-Combat-Integration.

Skripte lassen sich als `.txt` importieren. Zusätzliche Befehle:

```
mass tp quest
p1 entitytp "DM_Estate_Clue_01"
mass clickwindow "advanceDialogButton"
mass speed 100
mass restorespeed
```

Die bisherige feste Begrenzung auf 200 Schritte/15 Minuten und der Stop-Mechanismus bleiben.

### Angeln

Der Tab **Angeln** führt den vollständigen Originalkern aus `xLordTime/Fisch-Bot-DE` (Commit `c29dc5e183756b5409bd97ad5d776e9c01b73b15`) aus. Enthalten sind alle 31 Patches, Teicherneuerung, Filter, Fang-Popup-Bypass, automatische Korbleerung bei voller Tasche und nach 100 Fischen, optionaler Speedhack und sämtliche Timing-Einstellungen. Die Standardwerte entsprechen dem Original: Rang 2, Maximalgröße 999, Popup überspringen an, Speedhack aus, alle Patterns erforderlich. Web-Limits sind standardmäßig unbegrenzt (0).

Die originale GUI wird durch den Web-Tab ersetzt; vorhandene Bridge-Hooks werden wiederverwendet. Der Angelablauf bleibt im vendorten Originalcode. Ein gezielter Fehler im Original wird korrigiert: Bei ausgeschaltetem Popup-Bypass wird dessen Patch nicht gesetzt, damit das normale Fangfenster erscheinen kann.

Die Bridge sichert Code-Originalbytes vor Schreibzugriffen, prüft Schreiben und Wiederherstellung und räumt vor dem Enthooken auf. Auch ein nur teilweise eingerichteter Speedhack bleibt für das Aufräumen registriert. Fehler beim Zurückschreiben behalten die Sicherung und verhindern das Schließen betroffener Hooks. Stoppen ist kooperativ; laufende Tasten- und Mausaktionen werden nicht abgebrochen.

**Korbleerung:** Wie im Original kann der Bot dabei ausgewählte Fische löschen. Vor einem Zonenwechsel stoppen. Der reale Wizard101-DE-Spielablauf und der gemeldete Zonenabsturz konnten hier nicht getestet werden; automatisierte Tests führen den Originalkern gegen simulierte Spiel-APIs aus.

### Raid-Tools und Accounts

Im Tab **Raid** einen der fünf Raids wählen, seitlich den gewünschten Client auswählen und bei Bedarf **Hooken**. Die Suche filtert die Funktionen. Vor koordinatenbasierten Teleports die passende Raid-Teilzone betreten. **Aktion stoppen** beendet laufende Helfer; die Bridge entfernt dabei ihre Raid-Angelpatches. Touchstones setzen eine bereits aktive Freecam voraus. Raid-Angelpatches werden automatisch für den Fang aktiviert und danach entfernt.

Angeln und Raid besitzen eine eigene Account-Auswahl, unabhängig von der globalen Auswahl unter Hooking. Beim Wechsel wird eine laufende Aktion zuerst vollständig gestoppt. Falls die Wiederherstellung fehlschlägt, bleibt der alte Account ausgewählt. Der nächste Lauf wird manuell gestartet.

Original: [Lxghtend/raid-utility-tools](https://github.com/Lxghtend/raid-utility-tools), WorldsCollideTP von [CIick](https://github.com/CIick), GPL-3.0. Stand und Anpassungen: `bridge/vendor/raids/UPSTREAM.json`.
