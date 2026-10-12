'use strict';
const MW_SCRIPT_FUNCTIONS=[
  {
    "group": "Sprache",
    "syntax": "con count = 0",
    "note": "Variable/Zähler definieren",
    "status": "ready",
    "snippet": "con count = 0"
  },
  {
    "group": "Sprache",
    "syntax": "addone count",
    "note": "Zähler erhöhen",
    "status": "ready",
    "snippet": "addone count"
  },
  {
    "group": "Sprache",
    "syntax": "minusone count",
    "note": "Zähler verringern",
    "status": "ready",
    "snippet": "minusone count"
  },
  {
    "group": "Sprache",
    "syntax": "reset count",
    "note": "Zähler zurücksetzen",
    "status": "ready",
    "snippet": "reset count"
  },
  {
    "group": "Sprache",
    "syntax": "settimer farm",
    "note": "Zeitmessung starten",
    "status": "ready",
    "snippet": "settimer farm"
  },
  {
    "group": "Sprache",
    "syntax": "endtimer farm",
    "note": "Zeitmessung ausgeben",
    "status": "ready",
    "snippet": "endtimer farm"
  },
  {
    "group": "Sprache",
    "syntax": "if any incombat { … }",
    "note": "Bedingung mit any/sameany",
    "status": "ready",
    "snippet": "if any incombat { … }"
  },
  {
    "group": "Sprache",
    "syntax": "elif p1 loading { … }",
    "note": "Weitere Bedingung",
    "status": "ready",
    "snippet": "elif p1 loading { … }"
  },
  {
    "group": "Sprache",
    "syntax": "times 10 { … }",
    "note": "Kompakte Wiederholung",
    "status": "ready",
    "snippet": "times 10 { … }"
  },
  {
    "group": "Sprache",
    "syntax": "until any incombat { … }",
    "note": "Bedingung während der Ausführung überwachen",
    "status": "ready",
    "snippet": "until any incombat { … }"
  },
  {
    "group": "Sprache",
    "syntax": "block name { … }",
    "note": "Wiederverwendbarer Block",
    "status": "ready",
    "snippet": "block name { … }"
  },
  {
    "group": "Sprache",
    "syntax": "call safe_mob_pull",
    "note": "Standardbibliothek aufrufen",
    "status": "ready",
    "snippet": "call safe_mob_pull"
  },
  {
    "group": "Sprache",
    "syntax": "return",
    "note": "Block verlassen",
    "status": "ready",
    "snippet": "return"
  },
  {
    "group": "Sprache",
    "syntax": "break",
    "note": "Schleife verlassen",
    "status": "ready",
    "snippet": "break"
  },
  {
    "group": "Sprache",
    "syntax": "kill",
    "note": "Bot beenden",
    "status": "ready",
    "snippet": "kill"
  },
  {
    "group": "Sprache",
    "syntax": "restart_bot",
    "note": "Bot von vorne beginnen",
    "status": "ready",
    "snippet": "restart_bot"
  },
  {
    "group": "Sprache",
    "syntax": "p1 sendkey X && p2 sendkey X",
    "note": "Parallele Befehle",
    "status": "ready",
    "snippet": "p1 sendkey X && p2 sendkey X"
  },
  {
    "group": "Sprache",
    "syntax": "except p1 sendkey X",
    "note": "Alle ausgewählten Clients außer p1",
    "status": "ready",
    "snippet": "except p1 sendkey X"
  },
  {
    "group": "Sprache",
    "syntax": "p1:p3 sendkey X",
    "note": "Clientbereich",
    "status": "ready",
    "snippet": "p1:p3 sendkey X"
  },
  {
    "group": "Sprache",
    "syntax": "any incombat / sameany sendkey W",
    "note": "Passende Clients auswählen",
    "status": "ready",
    "snippet": "any incombat / sameany sendkey W"
  },
  {
    "group": "Bewegung",
    "syntax": "mass tp XYZ(100, 200, 0)",
    "note": "Direkte Position",
    "status": "ready",
    "snippet": "mass tp XYZ(100, 200, 0)"
  },
  {
    "group": "Bewegung",
    "syntax": "mass tp p1",
    "note": "Position von p1 übernehmen",
    "status": "ready",
    "snippet": "mass tp p1"
  },
  {
    "group": "Bewegung",
    "syntax": "mass tp closestmob",
    "note": "Nächsten Gegner ansteuern",
    "status": "ready",
    "snippet": "mass tp closestmob"
  },
  {
    "group": "Bewegung",
    "syntax": "mass tp quest",
    "note": "Questziel über Navmap ansteuern",
    "status": "ready",
    "snippet": "mass tp quest"
  },
  {
    "group": "Bewegung",
    "syntax": "p1 goto XYZ(100, 200, 0)",
    "note": "Zu einer Position laufen",
    "status": "ready",
    "snippet": "p1 goto XYZ(100, 200, 0)"
  },
  {
    "group": "Bewegung",
    "syntax": "p1 entitytp \"Chest\"",
    "note": "Entity nach Namen",
    "status": "ready",
    "snippet": "p1 entitytp \"Chest\""
  },
  {
    "group": "Bewegung",
    "syntax": "p1 tp + XYZ(0, 50, 0)",
    "note": "Relative Verschiebung",
    "status": "ready",
    "snippet": "p1 tp + XYZ(0, 50, 0)"
  },
  {
    "group": "Bewegung",
    "syntax": "p1 nav XYZ(100, 200, 0)",
    "note": "Navmap-Teleport",
    "status": "ready",
    "snippet": "p1 nav XYZ(100, 200, 0)"
  },
  {
    "group": "Bewegung",
    "syntax": "mass setyaw 1.57",
    "note": "Ausrichtung in Radiant",
    "status": "ready",
    "snippet": "mass setyaw 1.57"
  },
  {
    "group": "Bewegung",
    "syntax": "p1 freecam",
    "note": "MythicWalker-Freecam umschalten",
    "status": "ready",
    "snippet": "p1 freecam"
  },
  {
    "group": "Bewegung",
    "syntax": "p1 tp camera",
    "note": "Geprüfter Freecam-TP",
    "status": "ready",
    "snippet": "p1 tp camera"
  },
  {
    "group": "Bewegung",
    "syntax": "mass speed 100",
    "note": "Temporäre Geschwindigkeit",
    "status": "ready",
    "snippet": "mass speed 100"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass waitforbattle",
    "note": "Kampfstart abwarten",
    "status": "ready",
    "snippet": "mass waitforbattle"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass waitforbattle completion",
    "note": "Kampfende abwarten",
    "status": "ready",
    "snippet": "mass waitforbattle completion"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass waitfordialog",
    "note": "Dialog abwarten",
    "status": "ready",
    "snippet": "mass waitfordialog"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass waitforfree",
    "note": "Freien Spielzustand abwarten",
    "status": "ready",
    "snippet": "mass waitforfree"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass waitforzonechange",
    "note": "Zonenwechsel abwarten",
    "status": "ready",
    "snippet": "mass waitforzonechange"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass waitforwindow ['WorldView', 'NPCRangeWin']",
    "note": "UI-Pfad abwarten",
    "status": "ready",
    "snippet": "mass waitforwindow ['WorldView', 'NPCRangeWin']"
  },
  {
    "group": "UI und Warten",
    "syntax": "if any windowvisible ['WorldView', 'NPCRangeWin'] { … }",
    "note": "Sichtbarkeit prüfen",
    "status": "ready",
    "snippet": "if any windowvisible ['WorldView', 'NPCRangeWin'] { … }"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass clickwindow ['WorldView', 'wndDialogMain', 'advanceDialogButton']",
    "note": "UI-Pfad anklicken",
    "status": "ready",
    "snippet": "mass clickwindow ['WorldView', 'wndDialogMain', 'advanceDialogButton']"
  },
  {
    "group": "UI und Warten",
    "syntax": "p1 click 500, 300",
    "note": "Client-Koordinaten anklicken",
    "status": "ready",
    "snippet": "p1 click 500, 300"
  },
  {
    "group": "UI und Warten",
    "syntax": "p1 move_cursor 500, 300",
    "note": "Temporären virtuellen Cursor bewegen",
    "status": "ready",
    "snippet": "p1 move_cursor 500, 300"
  },
  {
    "group": "UI und Warten",
    "syntax": "mass sendkey PAGE_UP, .1",
    "note": "WizWalker-Tastenname",
    "status": "ready",
    "snippet": "mass sendkey PAGE_UP, .1"
  },
  {
    "group": "Status und Komfort",
    "syntax": "if any healthbelow 50% { … }",
    "note": "Lebenspunkte als Prozent",
    "status": "ready",
    "snippet": "if any healthbelow 50% { … }"
  },
  {
    "group": "Status und Komfort",
    "syntax": "if p1 mana > 20 { … }",
    "note": "Mana prüfen",
    "status": "ready",
    "snippet": "if p1 mana > 20 { … }"
  },
  {
    "group": "Status und Komfort",
    "syntax": "if p1 inzone \"WizardCity/WC_Hub\" { … }",
    "note": "Interne Zone vergleichen",
    "status": "ready",
    "snippet": "if p1 inzone \"WizardCity/WC_Hub\" { … }"
  },
  {
    "group": "Status und Komfort",
    "syntax": "if mass samezone { … }",
    "note": "Gemeinsame Zone prüfen",
    "status": "ready",
    "snippet": "if mass samezone { … }"
  },
  {
    "group": "Status und Komfort",
    "syntax": "if p1 hasxyz XYZ(100, 200, 0) { … }",
    "note": "Position vergleichen",
    "status": "ready",
    "snippet": "if p1 hasxyz XYZ(100, 200, 0) { … }"
  },
  {
    "group": "Status und Komfort",
    "syntax": "log p1 health",
    "note": "Status ausgeben",
    "status": "ready",
    "snippet": "log p1 health"
  },
  {
    "group": "Status und Komfort",
    "syntax": "if any potioncountbelow 1 { … }",
    "note": "Trankfüllung prüfen",
    "status": "ready",
    "snippet": "if any potioncountbelow 1 { … }"
  },
  {
    "group": "Status und Komfort",
    "syntax": "mass usepotion",
    "note": "Trank verwenden",
    "status": "ready",
    "snippet": "mass usepotion"
  },
  {
    "group": "Status und Komfort",
    "syntax": "mass buypotions ifneeded",
    "note": "Tränke bei Hilda; nur Commons",
    "status": "limited",
    "snippet": "mass buypotions ifneeded"
  },
  {
    "group": "Status und Komfort",
    "syntax": "p1 friendtp \"Name\"",
    "note": "Freundesliste nach Namen durchsuchen",
    "status": "limited",
    "snippet": "p1 friendtp \"Name\""
  },
  {
    "group": "Status und Komfort",
    "syntax": "p1 relog",
    "note": "Charakter ab- und wieder anmelden",
    "status": "ready",
    "snippet": "p1 relog"
  },
  {
    "group": "Combat",
    "syntax": "loadplaystyle \"…\"",
    "note": "Mehrzeiligen Playstyle laden",
    "status": "ready",
    "snippet": "loadplaystyle \"…\""
  },
  {
    "group": "Combat",
    "syntax": "togglecombat on",
    "note": "Kampfautomatik im Bot starten",
    "status": "ready",
    "snippet": "togglecombat on"
  },
  {
    "group": "Combat",
    "syntax": "any<damage&aoe>[Epic] @ enemies",
    "note": "Typfilter + Enchant + Ziel",
    "status": "ready",
    "snippet": "any<damage&aoe>[Epic] @ enemies"
  },
  {
    "group": "Combat",
    "syntax": "{1} any<blade> @ self",
    "note": "Rundenspezifische Priorität",
    "status": "ready",
    "snippet": "{1} any<blade> @ self"
  },
  {
    "group": "Combat",
    "syntax": "?(self.health < 30%) any<heal> @ self",
    "note": "Kampfbedingung",
    "status": "ready",
    "snippet": "?(self.health < 30%) any<heal> @ self"
  },
  {
    "group": "Combat",
    "syntax": "Feint[Potent Trap] @ boss | pass",
    "note": "Alternativen von links nach rechts",
    "status": "ready",
    "snippet": "Feint[Potent Trap] @ boss | pass"
  },
  {
    "group": "Combat",
    "syntax": "any<blade> @ ally(1)",
    "note": "Mitspieler als Ziel",
    "status": "ready",
    "snippet": "any<blade> @ ally(1)"
  },
  {
    "group": "Combat",
    "syntax": "draw(2) | any<damage> @ enemy",
    "note": "Karten ziehen",
    "status": "ready",
    "snippet": "draw(2) | any<damage> @ enemy"
  },
  {
    "group": "Combat",
    "syntax": "willcast @ enemy & any<damage> @ enemy",
    "note": "Pet-Karte und Zauber",
    "status": "ready",
    "snippet": "willcast @ enemy & any<damage> @ enemy"
  },
  {
    "group": "Grenzen",
    "syntax": "autopet",
    "note": "DE-Pet-Tanz-Hook noch nicht integriert",
    "status": "unavailable",
    "snippet": "autopet"
  },
  {
    "group": "Grenzen",
    "syntax": "tozone \"World/Zone\"",
    "note": "Weltübergreifender Navigator fehlt",
    "status": "unavailable",
    "snippet": "tozone \"World/Zone\""
  },
  {
    "group": "Grenzen",
    "syntax": "setdeck / getdeck",
    "note": "Deck-Preset-Adapter fehlt",
    "status": "unavailable",
    "snippet": "setdeck / getdeck"
  },
  {
    "group": "Grenzen",
    "syntax": "item_dropped",
    "note": "Drop-Tracking fehlt im DE-Adapter",
    "status": "unavailable",
    "snippet": "item_dropped"
  },
  {
    "group": "Grenzen",
    "syntax": "any<gambit(...)> / clear / echo / swap / req_met",
    "note": "Neuere Effektanforderungen fehlen",
    "status": "unavailable",
    "snippet": "any<gambit(...)> / clear / echo / swap / req_met"
  }
];
if(typeof module!=='undefined')module.exports=MW_SCRIPT_FUNCTIONS;
