from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPERATOR = ROOT / "scripts" / "operator"
START = OPERATOR / "Start-Orion.ps1"
STOP = OPERATOR / "Stop-Orion.ps1"
INSTALLER = OPERATOR / "Install-Orion-Desktop-Shortcuts.ps1"
HUD_HELPER = OPERATOR / "Hud-Operator.ps1"
README = OPERATOR / "README.md"


class TestOperatorLifecycleScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.start = START.read_text(encoding="utf-8")
        cls.stop = STOP.read_text(encoding="utf-8")
        cls.installer = INSTALLER.read_text(encoding="utf-8")
        cls.hud_helper = HUD_HELPER.read_text(encoding="utf-8")
        cls.readme = README.read_text(encoding="utf-8")

    def test_loopback_health_checks_explicitly_bypass_proxy(self):
        for name, text in (
            ("Start-Orion.ps1", self.start),
            ("Stop-Orion.ps1", self.stop),
            ("Hud-Operator.ps1", self.hud_helper),
        ):
            with self.subTest(script=name):
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

    def test_hud_launch_occurs_only_after_hermes_health(self):
        self.assertIn('$hudRoot = Join-Path $orionRoot "hud"', self.start)
        self.assertIn("Start-OrionHudBridge", self.start)
        self.assertIn("Open-OrionHud", self.start)
        self.assertIn("HudHealthTimeoutSeconds", self.start)
        hermes_wait = self.start.index(
            "Wait-DirectHttpEndpoint -Uri $hermesHealthUri -ExpectedUp $true"
        )
        hud_start = self.start.index("$hud = Start-OrionHudBridge")
        hud_open = self.start.index("Open-OrionHud -Uri")
        ready = self.start.index('Write-Host "ORION READY"')
        self.assertLess(hermes_wait, hud_start)
        self.assertLess(hud_start, hud_open)
        self.assertLess(hud_open, ready)

    def test_start_persists_recoverable_state_before_hud_failure_points(self):
        self.assertIn("schemaVersion = 2", self.start)
        self.assertIn("hudStartedByOrion", self.start)
        self.assertIn("hudPid", self.start)
        self.assertIn("hudProcessName", self.start)
        self.assertIn("hudExecutablePath", self.start)
        self.assertIn("hudCreationDate", self.start)
        self.assertIn("hudBridgePath", self.start)
        first_state_write = self.start.index("Write-OrionSessionState -State $state")
        hud_start = self.start.index("$hud = Start-OrionHudBridge")
        self.assertLess(first_state_write, hud_start)
        self.assertIn(
            "Launcher session state was preserved. Run Stop Orion to return to clean-off before retrying.",
            self.start,
        )

    def test_hud_helper_verifies_orion_identity_before_reuse_or_open(self):
        self.assertIn('$script:OrionHudUrl = "http://127.0.0.1:8765/"', self.hud_helper)
        self.assertIn('$script:OrionHudServerPrefix = "OrionHUD/2A"', self.hud_helper)
        self.assertIn(
            '$script:OrionHudTitleMarker = "<title>Orion // Personal AI Companion</title>"',
            self.hud_helper,
        )
        self.assertIn("function Test-OrionHudEndpoint", self.hud_helper)
        self.assertIn("$request.Proxy = $null", self.hud_helper)
        self.assertIn("function Get-OrionHudListenerPid", self.hud_helper)
        self.assertIn("occupied by unverified PID", self.hud_helper)
        self.assertIn("refusing to replace or claim it as the Orion HUD", self.hud_helper)
        self.assertIn("Open-OrionHud", self.hud_helper)
        self.assertIn(
            "refusing to open an unverified local page",
            self.hud_helper,
        )

    def test_hud_helper_requires_supported_python_and_installed_runtime(self):
        self.assertIn("function Resolve-OrionHudPython", self.hud_helper)
        self.assertIn("Python 3.11+", self.hud_helper)
        self.assertIn('Join-Path $HudRoot "orion_hud_bridge.py"', self.hud_helper)
        self.assertIn('Join-Path $HudRoot "action_projection.py"', self.hud_helper)
        self.assertIn('Join-Path $HudRoot "static\\index.html"', self.hud_helper)
        self.assertIn("-RedirectStandardOutput $stdoutPath", self.hud_helper)
        self.assertIn("-RedirectStandardError $stderrPath", self.hud_helper)

    def test_hud_ownership_is_identity_checked_and_never_claimed_by_port_only(self):
        self.assertIn("function Get-OrionHudMatchingProcess", self.hud_helper)
        self.assertIn("hudProcessName", self.hud_helper)
        self.assertIn("hudExecutablePath", self.hud_helper)
        self.assertIn("hudCreationDate", self.hud_helper)
        self.assertIn("hudBridgePath", self.hud_helper)
        self.assertIn("CommandLine", self.hud_helper)
        self.assertIn("function Get-OrionHudVerifiedProcessHandle", self.hud_helper)
        self.assertIn("$handle.StartTime", self.hud_helper)
        self.assertIn("$handle.MainModule.FileName", self.hud_helper)
        self.assertIn("pre-existing; ownership not claimed", self.hud_helper)

    def test_stop_cleans_only_identity_verified_orion_owned_hud(self):
        self.assertIn("Stop-OrionOwnedHudBridge -SessionState $sessionState", self.stop)
        self.assertIn("function Stop-OrionOwnedHudBridge", self.hud_helper)
        self.assertIn("$handle.Kill()", self.hud_helper)
        self.assertIn("$handle.WaitForExit(5000)", self.hud_helper)
        self.assertIn("leaving it alone", self.hud_helper)
        self.assertNotIn("Get-Process python | Stop-Process", self.hud_helper)
        self.assertNotIn("Get-Process -Name python | Stop-Process", self.hud_helper)
        self.assertLess(
            self.stop.index("Stop-OrionOwnedHudBridge -SessionState $sessionState"),
            self.stop.rindex("Remove-Item -LiteralPath $statePath -Force"),
        )

    def test_installer_publishes_self_contained_hud_runtime(self):
        self.assertIn('$sourceHudHelper = Join-Path $PSScriptRoot "Hud-Operator.ps1"', self.installer)
        self.assertIn('$sourceHudBridge = Join-Path $sourceHudRoot "orion_hud_bridge.py"', self.installer)
        self.assertIn('$sourceHudProjection = Join-Path $sourceHudRoot "action_projection.py"', self.installer)
        self.assertIn('$hudInstallRoot = Join-Path $orionRoot "hud"', self.installer)
        self.assertIn("Copy-Item -LiteralPath $sourceHudHelper", self.installer)
        self.assertIn("Copy-Item -LiteralPath $sourceHudBridge", self.installer)
        self.assertIn("Copy-Item -LiteralPath $sourceHudProjection", self.installer)
        self.assertIn('Copy-Item -Path (Join-Path $sourceHudStatic "*")', self.installer)
        self.assertIn("then accepted HUD", self.installer)

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

    def test_success_markers_follow_health_hud_and_shutdown_proof(self):
        self.assertLess(self.start.index("Ollama: ready"), self.start.index("ORION READY"))
        self.assertLess(self.start.index("Hermes COMPANION: ready"), self.start.index("ORION READY"))
        self.assertLess(self.start.index("Open-OrionHud -Uri"), self.start.index("ORION READY"))
        self.assertLess(self.stop.index("Wait-HermesDown"), self.stop.index("ORION STOPPED"))
        self.assertLess(
            self.stop.index("Stop-OrionOwnedHudBridge -SessionState $sessionState"),
            self.stop.index("ORION STOPPED"),
        )
        self.assertLess(
            self.stop.rindex("Stop-OrionOwnedDescendants -Snapshots $ownedDescendants"),
            self.stop.index("ORION STOPPED"),
        )

    def test_operator_readme_tracks_current_prd_rocm_and_hud_integration(self):
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
        self.assertIn("127.0.0.1:8765", self.readme)
        self.assertIn("after Hermes/API health", self.readme)
        self.assertIn("pre-existing HUD", self.readme)
        self.assertIn("Windows acceptance", self.readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
