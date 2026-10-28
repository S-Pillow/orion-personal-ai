from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPERATOR = ROOT / "scripts" / "operator"
START = OPERATOR / "Start-Orion.ps1"
STOP = OPERATOR / "Stop-Orion.ps1"
README = OPERATOR / "README.md"


class TestOperatorLifecycleScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = START.read_text(encoding="utf-8")
        cls.stop = STOP.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")

    def test_loopback_health_checks_explicitly_bypass_proxy(self):
        for name, text in (("Start-Orion.ps1", self.start), ("Stop-Orion.ps1", self.stop)):
            with self.subTest(script=name):
                self.assertIn("function Test-DirectHttpEndpoint", text)
                self.assertIn("$request.Proxy = $null", text)
                self.assertNotIn("Invoke-WebRequest", text)

    def test_start_uses_condition_based_health_waits(self):
        self.assertIn("function Wait-DirectHttpEndpoint", self.start)
        self.assertIn('$ollamaHealthUri = "http://127.0.0.1:11434/api/tags"', self.start)
        self.assertIn('$hermesHealthUri = "http://127.0.0.1:8642/health"', self.start)
        self.assertIn("-TimeoutSeconds $OllamaHealthTimeoutSeconds", self.start)
        self.assertIn("-TimeoutSeconds $HermesHealthTimeoutSeconds", self.start)
        self.assertRegex(
            self.start,
            r"\[int\]\$OllamaHealthTimeoutSeconds\s*=\s*(?:[3-9]\d|\d{3,})",
        )

    def test_start_pins_orion_started_ollama_to_rocm71_process_locally(self):
        self.assertIn('$ollamaLaunchLibrary = "rocm_v7_1"', self.start)
        self.assertIn("$previousOllamaLibrary = $env:OLLAMA_LLM_LIBRARY", self.start)
        self.assertIn("$env:OLLAMA_LLM_LIBRARY = $ollamaLaunchLibrary", self.start)
        self.assertIn("$env:OLLAMA_LLM_LIBRARY = $previousOllamaLibrary", self.start)
        self.assertLess(
            self.start.index("$env:OLLAMA_LLM_LIBRARY = $ollamaLaunchLibrary"),
            self.start.index("Start-Process"),
        )
        self.assertLess(
            self.start.index("Start-Process"),
            self.start.index("$env:OLLAMA_LLM_LIBRARY = $previousOllamaLibrary"),
        )
        self.assertIn("ollamaLibrary = $ollamaLibraryUsed", self.start)
        self.assertIn('Write-Host "Ollama backend: $ollamaLaunchLibrary"', self.start)

    def test_start_refuses_to_overwrite_pending_descendant_cleanup(self):
        self.assertIn('PSObject.Properties.Name -contains "ollamaDescendants"', self.start)
        self.assertIn('@($priorState.ollamaDescendants).Count -gt 0', self.start)
        self.assertIn(
            "Pending Orion-owned Ollama descendant cleanup exists. Run Stop Orion again before Start Orion.",
            self.start,
        )
        self.assertIn("ollamaDescendants = @()", self.start)
        self.assertLess(
            self.start.index("Pending Orion-owned Ollama descendant cleanup exists"),
            self.start.index("Start-Process"),
        )

    def test_start_captures_ollama_diagnostics(self):
        self.assertIn("-RedirectStandardOutput $ollamaStdoutPath", self.start)
        self.assertIn("-RedirectStandardError $ollamaStderrPath", self.start)
        self.assertIn("Ollama exited before becoming healthy", self.start)
        self.assertIn("Ollama bound port 11434 but direct health checks failed", self.start)
        self.assertIn("Ollama did not bind port 11434 or become healthy", self.start)
        self.assertIn("Backend: $ollamaLibraryUsed", self.start)

    def test_start_preserves_one_shot_ownership_model(self):
        self.assertIn("ollamaStartedByOrion", self.start)
        self.assertIn("ollamaPid", self.start)
        self.assertIn("Get-ListenerOwnerPid -Port 11434", self.start)
        self.assertNotIn("iai-mcp daemon start", self.start)
        self.assertNotIn("schtasks /Run", self.start)

    def test_stop_verifies_specific_owned_ollama_pid_exits(self):
        self.assertIn("ollamaStartedByOrion", self.stop)
        self.assertIn("Ollama: stopping Orion-owned server PID", self.stop)
        self.assertIn("Orion-owned Ollama PID $ownedPid is still running after stop attempt", self.stop)
        self.assertIn("leaving other Ollama processes alone", self.stop)
        self.assertNotIn("Get-Process ollama | Stop-Process", self.stop)

    def test_stop_cleans_only_snapshotted_owned_descendants(self):
        self.assertIn("function Get-OrionOwnedDescendantSnapshot", self.stop)
        self.assertIn("ParentProcessId", self.stop)
        self.assertIn("$processByPid", self.stop)
        self.assertIn("$parentProcess = $processByPid[$parentPid]", self.stop)
        self.assertIn(
            "[datetime]$child.CreationDate -lt [datetime]$parentProcess.CreationDate",
            self.stop,
        )
        self.assertIn("function Get-MatchingSnapshotProcess", self.stop)
        self.assertIn("function Get-VerifiedSnapshotProcessHandle", self.stop)
        self.assertIn("CreationDate", self.stop)
        self.assertIn("ExecutablePath", self.stop)
        self.assertIn("Get-CimInstance Win32_Process -ErrorAction Stop", self.stop)
        self.assertIn(
            'Get-CimInstance Win32_Process -Filter "ProcessId = $($Snapshot.ProcessId)" -ErrorAction Stop',
            self.stop,
        )
        self.assertIn(
            "$verifiedHandle = Get-VerifiedSnapshotProcessHandle -Snapshot $snapshot",
            self.stop,
        )
        self.assertIn("$processHandle.StartTime", self.stop)
        self.assertIn("$processHandle.MainModule.FileName", self.stop)
        self.assertIn("$verifiedHandle.Kill()", self.stop)
        self.assertIn("$verifiedHandle.WaitForExit(5000)", self.stop)
        self.assertNotIn("Stop-Process -Id ([int]$snapshot.ProcessId)", self.stop)
        self.assertNotIn("Get-Process llama-server | Stop-Process", self.stop)
        self.assertNotIn("Get-Process -Name llama-server | Stop-Process", self.stop)

    def test_stop_persists_descendants_before_parent_shutdown_and_retries_them(self):
        self.assertIn("function Write-OrionSessionState", self.stop)
        self.assertIn("function Get-PersistedOwnedDescendants", self.stop)
        self.assertIn("function Merge-OwnedDescendantSnapshots", self.stop)
        self.assertIn("function Save-OwnedDescendantSnapshots", self.stop)
        self.assertIn("function Stop-OrionOwnedDescendants", self.stop)
        self.assertIn('Add-Member -NotePropertyName "ollamaDescendants"', self.stop)
        self.assertIn(
            "Save-OwnedDescendantSnapshots -SessionState $sessionState -Snapshots $ownedDescendants",
            self.stop,
        )
        self.assertLess(
            self.stop.index(
                "Save-OwnedDescendantSnapshots -SessionState $sessionState -Snapshots $ownedDescendants"
            ),
            self.stop.index("Stop-Process -Id $ownedPid -ErrorAction SilentlyContinue"),
        )
        self.assertIn(
            "recorded parent is gone or no longer matches; retrying persisted Orion-owned descendant cleanup",
            self.stop,
        )
        self.assertIn("Stop-OrionOwnedDescendants -Snapshots $ownedDescendants", self.stop)
        self.assertLess(
            self.stop.rindex("Stop-OrionOwnedDescendants -Snapshots $ownedDescendants"),
            self.stop.rindex("Remove-Item -LiteralPath $statePath -Force"),
        )
        self.assertIn(
            "Launcher session state was retained for a safe Stop Orion retry when available.",
            self.stop,
        )

    def test_stop_accepts_empty_descendant_collections(self):
        self.assertGreaterEqual(self.stop.count("[AllowEmptyCollection()]"), 4)
        self.assertIn(
            "[AllowEmptyCollection()]\n        [object[]]$Existing",
            self.stop,
        )
        self.assertIn(
            "[AllowEmptyCollection()]\n        [object[]]$Fresh",
            self.stop,
        )
        self.assertIn(
            "[AllowEmptyCollection()]\n        [object[]]$Snapshots",
            self.stop,
        )

    def test_stop_leaves_iai_under_vendor_lifecycle(self):
        self.assertIn("iai remains under its vendor idle/HIBERNATION lifecycle", self.stop)
        self.assertNotIn("iai-mcp daemon stop", self.stop)
        self.assertNotIn("schtasks", self.stop)

    def test_success_markers_follow_health_or_shutdown_proof(self):
        self.assertLess(self.start.index("Ollama: ready"), self.start.index("ORION READY"))
        self.assertLess(self.start.index("Hermes COMPANION: ready"), self.start.index("ORION READY"))
        self.assertLess(self.stop.index("Wait-HermesDown"), self.stop.index("ORION STOPPED"))
        self.assertLess(
            self.stop.rindex("Stop-OrionOwnedDescendants -Snapshots $ownedDescendants"),
            self.stop.index("ORION STOPPED"),
        )

    def test_operator_readme_tracks_current_prd_and_rocm_correction(self):
        self.assertIn("Master PRD v2.9", self.readme)
        self.assertNotIn("Master PRD v2.8", self.readme)
        self.assertNotIn("Current Phase 2 relationship", self.readme)
        self.assertIn("rocm_v7_1", self.readme)
        self.assertIn("process-local", self.readme)
        self.assertIn("does not rewrite", self.readme)
        self.assertIn("descendant", self.readme)
        self.assertIn("identity-checked", self.readme)
        self.assertIn("creation order", self.readme)
        self.assertIn("pending cleanup", self.readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
