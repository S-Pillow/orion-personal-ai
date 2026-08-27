# SP4B v2 disposable rebuild closure

## Disposition

**PASS / CLOSED**

Accepted August 27, 2026.

## Source fix

Commit:

`e4ba3f91f0d1eb238f3e5f7e32a9349e87788a8a`

Message:

`build: fix disposable F5E acquisition dependency`

## Validation result

- canonical build: PASS
- F5E model hashes: PASS
- iai-pme 3.0.8: PASS
- iai Python 3.12: PASS
- `recent_thread` serializer: PASS
- ddgs 9.14.4: PASS
- rebuilt final image functional verification: PASS
- accepted runtime unchanged: PASS
- accepted iai data volume not mounted by disposable rebuild: PASS
- accepted container not restarted: PASS

Rebuilt final image ID:

`sha256:d783e158062d865b1893306a0b835c576ee6e77a16e29ff41bb59354cade847e`

Retained local evidence:

`E:\Orion-Phase2\SP4B-V2-REBUILD-20260827-073739Z\02-summary.txt`

## Claim boundary

SP4B v2 proves functional source rebuildability for the validated Orion runtime
contracts. It does not claim byte-identical Docker image reproduction and it does not
change iai's accepted MVP memory semantics.
