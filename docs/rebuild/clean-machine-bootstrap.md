# Orion clean-machine source and recovery procedure

This procedure prevents Orion from depending on one workstation.

## Source repositories

Clone:

- `S-Pillow/orion-personal-ai`
- `S-Pillow/jarvis_ai`
- `S-Pillow/iai-personal-memory-engine`

The Orion HUD uses the `orion-mvp` branch of `jarvis_ai`.
The iai fork tracks upstream compatibility; upstream iai semantics remain controlling.

## Recovery helper

From `orion-personal-ai`, plan only:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\rebuild\Prepare-Orion-Recovery-Workspace.ps1"
```

Prepare the source workspace:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\rebuild\Prepare-Orion-Recovery-Workspace.ps1" -ExecuteSourceSetup
```

Prepare source and execute the canonical runtime rebuild:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\rebuild\Prepare-Orion-Recovery-Workspace.ps1" -ExecuteSourceSetup -BuildRuntime
```

The helper uses `orion-recovery-*` rebuild tags. It does not restore personal data or
credentials automatically.

## Private recovery material

Keep these outside public GitHub:

- provider/API credentials;
- Discord credentials if used;
- a valid native iai backup and/or the iai encryption key;
- the Obsidian vault;
- intentionally retained private exports/backups.

## SP4B v2 evidence

Functional disposable rebuild passed on August 27, 2026.

- source-fix commit: `e4ba3f91f0d1eb238f3e5f7e32a9349e87788a8a`
- rebuilt final image ID: `sha256:d783e158062d865b1893306a0b835c576ee6e77a16e29ff41bb59354cade847e`
- iai Python 3.12: PASS
- iai-pme 3.0.8: PASS
- pinned BGE artifact hashes: PASS
- `recent_thread` serializer: PASS
- ddgs 9.14.4: PASS
- accepted live Orion runtime: unchanged

The rebuilt image is functionally equivalent for the validated contracts. This is not a
byte-identical Docker-image claim.
