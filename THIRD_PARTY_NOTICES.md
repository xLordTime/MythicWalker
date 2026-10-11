# Third-party notices

WizWalker — Wizard101 scripting library.
Original author as declared by upstream: StarrFox. DE/EU fork: Vindaloniak. Deimos-maintained upstream: Deimos-Wizard101.
License declared in upstream pyproject.toml: GPL-3.0-or-later.
Source used: https://github.com/Vindaloniak/wizwalker/tree/13223e0911578e586975ace496d9f586ac4538da
The full GPL license text is included in LICENSE. WizWalker is installed as a dependency, rather than copied into this repository.

Bridge dependencies: aiohttp (Apache-2.0), cryptography (Apache-2.0 or BSD-3-Clause). Their transitive dependencies retain their own notices in the installed packages. PyInstaller is only used for optional Windows packaging; its distribution and bootloader license applies to those builds.

Other repositories named in README and sources.json were examined as references or found in repository search. Their code is not incorporated into this project.

## Adapted Deimos navmap implementation

`bridge/navmap.py` is adapted from `Deimos-Wizard101/Deimos-Wizard101`,
`src/teleport_math.py`, commit `d7ef56eb51c5b5316cadba40ca554ec442a5dcee`, GPL-3.0.
The embedded nav parser originated from PeechezNCreem/navwiz and retains its
complete Boost Software License 1.0 notice in that file. Changes isolate the
WizWalker adapter, bound operations, and limit the final walk distance.

## Deimos bot registry and NPC behavior reference

`dist/upstream-bots.json` and its EXE copy bundle unchanged scripts from Deimos-Wizard101/bots, commit `dc5198b1a8570fa169c45fdd2c01768b5da757e0`, licensed GPL-3.0. Fork: https://github.com/xLordTime/bots. Original author metadata and source paths are preserved. Full upstream license text: `dist/BOTS_LICENSE.txt`. The MythicWalker example and default blocks are additional GPL-3.0 project content.

The read-only hostile NPCBehavior flag used by `closest_mob` follows `src/sprinty_client.py` in Deimos-Wizard101/Deimos-Wizard101 (GPL-3.0; SprintyClient credits Sirolaf). No full Deimos VM or Playstyle parser is bundled.
