# Research evidence

Collected on 3 November 2026. Start with the [consolidated research](<../mission-editor-research.md>); the [verification report](<../mission-editor-feasibility-update.md>) retains the detailed source discussion and experiment matrix.

- `installed-game-audit.json`: local EW package headers, map configuration, selected properties, class/export counts, relevant file hashes and custom-material executable signature counts. These are static observations, not gameplay tests.
- `executable-pattern-audit.json`: an additional read-only check of all four patterns in LWCE's executable patch notes, including offsets. No patch was applied.
- `upstream/source-manifest.json`: exact public source URLs, repository revisions and local SHA-256 values. The adjacent source files are retained unmodified for research; their original attribution remains intact.
- `upstream/*-tree.json`: GitHub repository tree snapshots used to locate relevant source files. These are file listings, not complete repository downloads.
- `forum-and-wiki-notes-2026-11-03.md`: notes from reading the Nexus "R&D XCOM Map Alterations" thread (pages 7–48) and five Nexus wiki pages. These are claims made by the original authors in 2013–2015, not reproduced. The file also covers the August 2026 Reddit thread, read from the user's paste.
- `experiment-downloads-2026-11-03.json`: public release metadata checked for the investigation plan, including exact filenames, download sizes, URLs and publisher digests where available. Only metadata was retrieved; the installers/archives were not downloaded or run.

Reproduce the main audit in PowerShell from the project directory:

```powershell
& 'python' -I `
  '<repo>\tools\upk\audit_install.py' `
  '<Steam common>\XCom-Enemy-Unknown' `
  '<repo>\research\evidence\installed-game-audit.json'
```

Another Python 3.11+ interpreter can be substituted. The Windows Store `python.exe` alias did not run in this session, so the installed uv-managed interpreter was used. The audit refuses an output path inside the game directory. It reads game packages and the executable, writes only its requested JSON output, and uses the project's existing experimental v845 parsers. Twelve packages need outer-LZO header decoding, which the audit handles separately; the older general-purpose readers were not changed.

The audit's native-tail byte counts describe how much data remains after tagged properties. They do not decode world-data-container semantics. Export counts include default objects and duplicated assets; absence/presence in these tables does not by itself demonstrate correct runtime behavior.
