# -*- coding: utf-8 -*-
"""GitHub release bootstrap guard tests; no real network, repository, or credentials are used."""
import re
import unittest
from pathlib import Path
import Prepare_Release as release

ROOT = Path(__file__).resolve().parent


class GitHubBootstrapSafetyTests(unittest.TestCase):
    def setUp(self):
        self.script = (ROOT / 'Setup_GitHub_AutoRelease.ps1').read_text(encoding='utf-8')
        self.workflow = (ROOT / 'release_workflow_template.yml').read_text(encoding='utf-8')
        self.server = (ROOT / 'ShortCompassServer.py').read_text(encoding='utf-8')
        self.launcher = (ROOT / 'Setup_GitHub_AutoRelease.bat').read_text(encoding='utf-8')

    def test_bootstrap_requires_existing_gh_session(self):
        self.assertIn("Invoke-CheckedCommand -Executable 'gh' -Arguments @('auth', 'status')", self.script)
        self.assertIn("gh api user --jq '.login'", self.script)
        self.assertNotRegex(self.script, r'ghp_[A-Za-z0-9]{30,}')
        self.assertNotRegex(self.script, r'github_pat_[A-Za-z0-9_]{30,}')

    def test_default_is_public_for_anonymous_auto_updates_with_explicit_confirmation(self):
        self.assertRegex(self.script, r"\[string\]\$Visibility\s*=\s*'Public'")
        self.assertIn("ValidateSet('Private', 'Public')", self.script)
        self.assertIn('Public 저장소는 소스 코드와 릴리스 자산을 누구나 볼 수 있습니다', self.script)
        self.assertIn("공개 저장소에서는 허용 목록에 포함된 프로그램 소스와 문서가 누구나 볼 수 있게 됩니다.", self.script)
        self.assertNotIn('[switch]$Yes', self.script)

    def test_double_click_launcher_invokes_guarded_powershell_setup_and_keeps_log(self):
        self.assertIn('Setup_GitHub_AutoRelease.ps1', self.launcher)
        self.assertIn('-ExecutionPolicy Bypass', self.launcher)
        self.assertIn('pause', self.launcher.lower())
        self.assertIn('github-autorelease-setup.log', self.launcher)
        self.assertIn('-LogPath', self.launcher)
        self.assertIn('Setup_GitHub_AutoRelease.bat', self.script)
        # Windows PowerShell 5.1 needs a UTF-8 BOM to decode Korean diagnostics correctly.
        self.assertTrue((ROOT / 'Setup_GitHub_AutoRelease.ps1').read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_launcher_reenters_same_console_with_cmd_k_and_keeps_failure_visible(self):
        launcher_path = ROOT / 'Setup_GitHub_AutoRelease.bat'
        raw = launcher_path.read_bytes()
        self.assertFalse(raw.startswith(b'\xef\xbb\xbf'), 'cmd.exe launcher must be BOM-free')
        self.assertIn('cmd.exe /k ""%~f0" %*"', self.launcher)
        self.assertIn('SHORTCOMPASS_KEEP_OPEN_247', self.launcher)
        self.assertIn('PowerShell exit code', self.launcher)
        self.assertIn('SETUP STOPPED. Exit code:', self.launcher)
        self.assertIn('type "%LOGFILE%"', self.launcher)
        self.assertIn('The console will remain open', self.launcher)

    def test_app_launcher_checks_health_keeps_diagnostics_and_preserves_server_console(self):
        app_launcher = (ROOT / 'Start_ShortCompass.bat').read_text(encoding='utf-8-sig')
        server_launcher = (ROOT / 'Start_ShortCompass_Server.bat').read_text(encoding='utf-8-sig')
        self.assertIn('Start_ShortCompass_Server.bat', app_launcher)
        self.assertIn('http://127.0.0.1:8765/health', app_launcher)
        self.assertIn("'2.47'", app_launcher)
        self.assertIn('start-shortcompass.log', app_launcher)
        self.assertIn('pause', app_launcher.lower())
        self.assertIn('py -3 -u', server_launcher)
        self.assertIn('python -u', server_launcher)
        self.assertIn('start-shortcompass.log', server_launcher)
        self.assertIn('pause', server_launcher.lower())
        self.assertNotIn('for /f', app_launcher.lower())
        self.assertIn('HEALTH_CODE', app_launcher)

    def test_installer_offers_consented_winget_install_and_browser_login(self):
        self.assertIn('Windows 패키지 관리자 winget으로 위 도구를 설치할 수 있습니다', self.script)
        self.assertIn("'INSTALL'", self.script)
        self.assertIn('GitHub.cli', self.script)
        self.assertIn("'auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https'", self.script)
        self.assertIn('필수 도구가 없습니다', self.script)

    def test_repository_prompt_accepts_name_full_name_or_github_url(self):
        self.assertIn('owner/repo, 저장소 URL 또는 Projects 보드 URL 입력', self.script)
        self.assertIn("$InputValue -match '^https://github\\.com/'", self.script)
        self.assertIn("$InputUri.Host -ne 'github.com'", self.script)
        self.assertIn("$InputValue -match '^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$'", self.script)
        self.assertIn('$FullRepository = "$RepositoryOwner/$RepositoryName"', self.script)
        self.assertIn("$RemoteRepositoryInfo.can_push -ne $true", self.script)

    def test_existing_empty_or_starter_repository_can_be_reused_safely(self):
        self.assertIn('RemoteRepositoryExists', self.script)
        self.assertIn("'repo', 'clone', $FullRepository, $WorkspacePath", self.script)
        self.assertIn('USE-EXISTING', self.script)
        self.assertIn('SHORTCOMPASS_RELEASE_GUIDE.md', self.script)
        self.assertIn('README.md', self.script)
        self.assertIn('$ExistingIgnoreLines', self.script)
        self.assertIn('기존 저장소에 허용되지 않은 파일이 있어 자동 변경을 중단했습니다', self.script)
        self.assertIn('$FullRepository = "$RepositoryOwner/$RepositoryName"', self.script)
        self.assertIn("Read-Host '계속하려면 CREATE를 입력하세요'", self.script)

    def test_setup_errors_are_logged_with_failed_step_and_no_secret_values(self):
        self.assertIn('function Write-SetupLog', self.script)
        self.assertIn('실패 단계:', self.script)
        self.assertIn('실패 원인:', self.script)
        self.assertIn('github-autorelease-setup.log', self.script)
        self.assertNotRegex(self.script, r'ghp_[A-Za-z0-9]{30,}')
        self.assertNotRegex(self.script, r'github_pat_[A-Za-z0-9_]{30,}')

    def test_projects_board_url_is_parsed_and_items_resolve_repository_candidates(self):
        self.assertIn("^https://github\\.com/(users|orgs)/([A-Za-z0-9_.-]+)/projects/(\\d+)", self.script)
        self.assertIn('gh project item-list', self.script)
        self.assertIn("'auth', 'refresh', '-s', 'project'", self.script)
        self.assertIn("USE-PROJECT-REPO", self.script)
        self.assertIn("https?://(?:api\\.)?github\\.com/(?:repos/)?", self.script)
        self.assertIn('프로젝트 보드에서 소스 저장소를 특정할 issue/PR 링크를 찾지 못했습니다', self.script)
        self.assertIn('Projects 보드 URL은 프로젝트 조회 후 저장소를 별도 선택해야 합니다', self.script)

    def test_batch_launcher_prints_help_lines_instead_of_executing_korean_as_command(self):
        self.assertIn('echo 기존 저장소도 README/.gitignore와 .github/workflows/release.yml만 있으면 이어서 설정할 수 있습니다.', self.launcher)
        self.assertIn('https://github.com/goldensw1130/-sw', self.launcher)

    def test_project_owner_mismatch_never_silently_targets_the_wrong_account(self):
        self.assertIn("'SWITCH-ACCOUNT'", self.script)
        self.assertIn('gh auth switch --hostname github.com --user $ProjectOwner', self.script)
        self.assertIn('$RepositoryOwner = $ProjectOwner', self.script)
        self.assertIn('계정 전환 후에도 로그인 계정이 보드 소유자와 다릅니다', self.script)

    def test_project_owner_mismatch_and_access_failure_are_explained(self):
        self.assertIn('보드 소유자({0})와 현재 gh 로그인({1})이 다릅니다', self.script)
        self.assertIn('프로젝트 보드는 현재 로그인으로 조회할 수 없습니다', self.script)
        self.assertIn('gh auth status', self.script)
        self.assertIn('저장소 URL, owner/repo 또는 새 저장소 이름을 직접 입력', self.script)

    def test_success_registers_public_update_feed_without_overwriting_custom_url(self):
        self.assertIn('function Register-UpdateFeedForCurrentUser', self.script)
        self.assertIn("$SettingsPath = Join-Path $DataDirectory 'update_settings.json'", self.script)
        self.assertIn("Register-UpdateFeedForCurrentUser -ManifestUrl $ManifestUrl", self.script)
        self.assertIn('다른 manifest URL이 이미 설정되어 있어 기존 업데이트 설정을 유지했습니다', self.script)
        self.assertIn('autoDownload = $AutoDownload', self.script)
        self.assertIn('$AutoDownload = $false', self.script)
        self.assertIn('if (-not $NoWait)', self.script)

    def test_explicit_source_allowlist_matches_update_allowlist(self):
        match = re.search(r'(?s)\$SourceFiles\s*=\s*@\((.*?)\)', self.script)
        self.assertIsNotNone(match)
        staged_names = re.findall(r"'([^']+)'", match.group(1))
        packaged_names = release.allowed_package_files(ROOT / 'ShortCompassServer.py')
        self.assertEqual(set(staged_names), set(packaged_names))
        self.assertEqual(len(staged_names), len(set(staged_names)))
        self.assertIn('Setup_GitHub_AutoRelease.bat', staged_names)

    def test_tests_and_release_preflight_run_before_repository_creation(self):
        self.assertIn('Test_GitHubBootstrap.py', self.script)
        self.assertIn("'Prepare_Release.py'", self.script)
        preflight = self.script.index("Invoke-CheckedCommand -Executable 'python' -Arguments @('Prepare_Release.py'")
        create_repo = self.script.index("Invoke-CheckedCommand -Executable 'gh' -Arguments $CreateArguments")
        self.assertLess(preflight, create_repo)
        self.assertLess(self.script.index("Read-Host '계속하려면 CREATE를 입력하세요'"), self.script.index('# Copy only named project files'))
        self.assertLess(self.script.index("Read-Host '계속하려면 CREATE를 입력하세요'"), create_repo)
        self.assertIn("'diff', '--cached', '--check'", self.script)

    def test_workflow_is_tag_triggered_and_uses_minimum_write_scope(self):
        self.assertIn("branches:\n      - main", self.workflow)
        self.assertIn("tags:\n      - 'v*'", self.workflow)
        self.assertIn("startsWith(github.event.head_commit.message, 'release:')", self.workflow)
        self.assertIn('tag_name: v${{ steps.release-version.outputs.version }}', self.workflow)
        self.assertIn('permissions:\n  contents: write', self.workflow)
        self.assertNotIn('permissions: write-all', self.workflow)
        self.assertIn('persist-credentials: false', self.workflow)
        self.assertIn('Test_GitHubBootstrap.py', self.workflow)

    def test_user_agents_follow_central_app_version(self):
        self.assertIn("'User-Agent':'ShortCompass-Updater/'+APP_VERSION", self.server)
        self.assertIn("'User-Agent':'ShortCompass-AI/'+APP_VERSION", self.server)

    def test_defaults_target_user_repository_and_unique_workspace_for_retries(self):
        self.assertIn("$RepositoryName = '-sw'", self.script)
        self.assertIn("$DefaultRepositoryUrl = 'https://github.com/goldensw1130/-sw'", self.script)
        self.assertIn("ShortCompass-ReleaseRepo-\" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')", self.script)
        self.assertIn("$InputValue = if ([string]::IsNullOrWhiteSpace($RepositoryInput)) { $DefaultRepositoryUrl }", self.script)

    def test_existing_release_workflow_only_is_allowed_and_replaced_by_current_template(self):
        self.assertIn(r"\.github/workflows/release\.yml", self.script)
        self.assertIn("Copy-Item -LiteralPath (Join-Path $WorkspacePath 'release_workflow_template.yml') -Destination (Join-Path $WorkflowDirectory 'release.yml') -Force", self.script)

    def test_repository_owner_account_mismatch_has_explicit_switch_and_verification(self):
        self.assertIn("소유자 {0}로 계정 전환을 시도하려면 SWITCH-ACCOUNT", self.script)
        self.assertIn("gh auth switch --hostname github.com --user $RepositoryOwner", self.script)
        self.assertIn("계정 전환 후 로그인 계정이 저장소 소유자와 일치하지 않습니다", self.script)


    def test_missing_dependencies_resume_in_fresh_powershell_after_winget(self):
        self.assertIn('[switch]$SkipDependencyInstall', self.script)
        self.assertIn('function Refresh-SetupPath', self.script)
        self.assertIn('function Get-MissingSetupCommands', self.script)
        self.assertIn('새 PowerShell 창에서 설정을 이어갑니다', self.script)
        self.assertIn("'-SkipDependencyInstall'", self.script)
        self.assertIn('새 PowerShell에서도 다음 도구를 찾을 수 없습니다', self.script)
        self.assertIn('설치가 진행되는 동안 창을 닫거나 아무 키나 누르지 마세요', self.script)

    def test_install_sequence_has_visible_progress_and_does_not_silently_claim_setup_done(self):
        self.assertIn('[{0}/{1}] {2} 설치를 시작합니다.', self.script)
        self.assertIn('필수 도구 경로 확인 완료. GitHub 로그인 및 저장소 설정 단계로 이어갑니다.', self.script)
        self.assertIn('ResumeExitCode', self.script)
        self.assertIn('새 PowerShell 프로세스에서 설정 이어서 실행이 정상 종료되었습니다.', self.script)


if __name__ == '__main__':
    unittest.main(verbosity=2)
