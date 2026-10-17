[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_.-]{1,100}$')]
    [string]$RepositoryName = '-sw',

    [ValidateSet('Private', 'Public')]
    [string]$Visibility = 'Public',

    [string]$WorkspacePath = (Join-Path $HOME ("ShortCompass-ReleaseRepo-" + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))),

    [string]$LogPath = '',

    [switch]$NoWait,

    # Used only after winget has installed prerequisites and PATH must be reloaded in a fresh process.
    [switch]$SkipDependencyInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:CurrentStep = '초기화'
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        $LogPath = Join-Path $env:LOCALAPPDATA 'ShortCompass\logs\github-autorelease-setup.log'
    } else {
        $LogPath = Join-Path $PSScriptRoot 'github-autorelease-setup.log'
    }
}

function Write-SetupLog {
    param([Parameter(Mandatory = $true)][string]$Message)
    try {
        $LogDirectory = Split-Path -Parent $LogPath
        if ($LogDirectory -and -not (Test-Path -LiteralPath $LogDirectory -PathType Container)) {
            New-Item -ItemType Directory -Path $LogDirectory -Force | Out-Null
        }
        $Line = '[{0}] {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
        Add-Content -LiteralPath $LogPath -Value $Line -Encoding UTF8
    } catch {
        # Logging failure must not hide the actual setup error.
    }
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][string]$Step
    )
    $script:CurrentStep = $Step
    Write-SetupLog ("시작: {0} ({1})" -f $Step, $Executable)
    Write-Host ("`n> {0} {1}" -f $Executable, ($Arguments -join ' ')) -ForegroundColor DarkGray
    & $Executable @Arguments
    $CommandExitCode = $LASTEXITCODE
    if ($CommandExitCode -ne 0) {
        Write-SetupLog ("실패: {0}, 종료 코드 {1}" -f $Step, $CommandExitCode)
        throw ("'{0}' 단계가 종료 코드 {1}로 실패했습니다. 작업 폴더를 보존했습니다: {2}. 로그: {3}" -f $Step, $CommandExitCode, $WorkspacePath, $LogPath)
    }
    Write-SetupLog ("완료: {0}" -f $Step)
}

function Get-CheckedText {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "필수 파일이 없습니다: $Path"
    }
    return [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
}

function Refresh-SetupPath {
    # Refresh registry-backed PATH values after winget installations and add common per-user paths.
    $MachinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $PathParts = New-Object System.Collections.Generic.List[string]
    foreach ($Part in @($MachinePath -split ';') + @($UserPath -split ';') + @($env:Path -split ';')) {
        if (-not [string]::IsNullOrWhiteSpace($Part)) {
            $Expanded = [Environment]::ExpandEnvironmentVariables($Part.Trim().Trim('"'))
            if ($Expanded -and (Test-Path -LiteralPath $Expanded -PathType Container) -and -not $PathParts.Contains($Expanded)) { $PathParts.Add($Expanded) }
        }
    }
    $CommonPaths = @(
        (Join-Path $env:ProgramFiles 'Git\cmd'),
        (Join-Path $env:ProgramFiles 'Git\bin'),
        (Join-Path $env:ProgramFiles 'GitHub CLI'),
        (Join-Path $env:ProgramFiles 'nodejs'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd'),
        (Join-Path $env:LOCALAPPDATA 'Programs\GitHub CLI'),
        (Join-Path $env:LOCALAPPDATA 'Programs\nodejs'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links')
    )
    foreach ($CommonPath in $CommonPaths) {
        if ($CommonPath -and (Test-Path -LiteralPath $CommonPath -PathType Container) -and -not $PathParts.Contains($CommonPath)) { $PathParts.Add($CommonPath) }
    }
    $PythonRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $PythonRoot -PathType Container) {
        foreach ($PythonDirectory in (Get-ChildItem -LiteralPath $PythonRoot -Directory -ErrorAction SilentlyContinue)) {
            if (-not $PathParts.Contains($PythonDirectory.FullName)) { $PathParts.Add($PythonDirectory.FullName) }
            $ScriptsDirectory = Join-Path $PythonDirectory.FullName 'Scripts'
            if ((Test-Path -LiteralPath $ScriptsDirectory -PathType Container) -and -not $PathParts.Contains($ScriptsDirectory)) { $PathParts.Add($ScriptsDirectory) }
        }
    }
    $env:Path = $PathParts -join ';'
}

function Get-MissingSetupCommands {
    $RequiredNames = @('git', 'gh', 'python', 'node')
    return @($RequiredNames | Where-Object { -not (Get-Command $_ -CommandType Application -ErrorAction SilentlyContinue) })
}

function Register-UpdateFeedForCurrentUser {
    param([Parameter(Mandatory = $true)][string]$ManifestUrl)
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        Write-Warning 'LOCALAPPDATA 환경 변수가 없어 사용자 업데이트 피드를 자동 등록하지 못했습니다. 앱의 업데이트 센터에 manifest URL을 직접 넣으세요.'
        return
    }
    $DataDirectory = Join-Path $env:LOCALAPPDATA 'ShortCompass'
    $SettingsPath = Join-Path $DataDirectory 'update_settings.json'
    $Existing = $null
    if (Test-Path -LiteralPath $SettingsPath -PathType Leaf) {
        try {
            $Existing = (Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8) | ConvertFrom-Json
        } catch {
            Write-Warning '기존 업데이트 설정 JSON을 읽을 수 없어 덮어쓰지 않았습니다. 앱의 업데이트 센터에서 manifest URL을 직접 설정하세요.'
            return
        }
        $ExistingUrlProperty = $Existing.PSObject.Properties['manifestUrl']
        $ExistingUrl = if ($null -ne $ExistingUrlProperty) { [string]$ExistingUrlProperty.Value } else { '' }
        if (-not [string]::IsNullOrWhiteSpace($ExistingUrl) -and $ExistingUrl -ne $ManifestUrl) {
            Write-Warning '다른 manifest URL이 이미 설정되어 있어 기존 업데이트 설정을 유지했습니다. 필요하면 앱의 업데이트 센터에서 새 주소를 등록하세요.'
            return
        }
    }
    $AutoCheck = $true
    $AutoDownload = $false
    $IntervalHours = 24
    if ($null -ne $Existing) {
        $Property = $Existing.PSObject.Properties['autoCheck']
        if ($null -ne $Property) { $AutoCheck = [bool]$Property.Value }
        $Property = $Existing.PSObject.Properties['autoDownload']
        if ($null -ne $Property) { $AutoDownload = [bool]$Property.Value }
        $Property = $Existing.PSObject.Properties['intervalHours']
        if ($null -ne $Property) {
            try { $IntervalHours = [Math]::Max(1, [Math]::Min(168, [int]$Property.Value)) } catch { $IntervalHours = 24 }
        }
    }
    $Settings = [ordered]@{
        manifestUrl = $ManifestUrl
        autoCheck = $AutoCheck
        autoDownload = $AutoDownload
        intervalHours = $IntervalHours
    }
    New-Item -ItemType Directory -Path $DataDirectory -Force | Out-Null
    $Json = ($Settings | ConvertTo-Json -Depth 4) + "`n"
    [System.IO.File]::WriteAllText($SettingsPath, $Json, [System.Text.UTF8Encoding]::new($false))
    Write-Host '현재 Windows 사용자용 업데이트 manifest 주소를 등록했습니다. 자동 다운로드는 안전을 위해 끈 상태이며, 업데이트 적용에는 사용자의 승인이 필요합니다.' -ForegroundColor Green
}

Write-SetupLog '=== GitHub 자동 릴리스 설정 시작 ==='
Write-SetupLog ("스크립트 경로: {0}" -f $PSScriptRoot)
try {
$script:CurrentStep = '설치 파일 검사'
$SourceRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ServerPath = Join-Path $SourceRoot 'ShortCompassServer.py'
$ServerText = Get-CheckedText -Path $ServerPath
$VersionMatch = [regex]::Match($ServerText, '(?m)^APP_VERSION\s*=\s*[''"]([^''"]+)[''"]')
if (-not $VersionMatch.Success) { throw 'ShortCompassServer.py에서 APP_VERSION을 읽을 수 없습니다.' }
$Version = $VersionMatch.Groups[1].Value
if ($Version -notmatch '^\d+(\.\d+){1,3}$') { throw "허용하지 않는 앱 버전입니다: $Version" }
$Tag = "v$Version"

$SourceFiles = @(
    'ShortsCompass.html',
    'ShortCompassServer.py',
    'Start_ShortCompass.bat',
    'Start_ShortCompass_Server.bat',
    'Start_Here_KO.txt',
    'Changes_KO.txt',
    'Test_KO.txt',
    'Test_ShortCompass.py',
    'Test_ABReliability.js',
    'Test_OpportunityLearning.js',
    'Test_YouTubeRanking.js',
    'Test_UpdateAndAI.py',
    'Test_UpdateUI.js',
    'Test_FullDiagnosticsUI.js',
    'Test_ReleaseTools.py',
    'Test_GitHubBootstrap.py',
    'Prepare_Release.py',
    'RELEASE_PUBLISHING_GUIDE_KO.md',
    'RELEASE_NOTES_CURRENT_KO.txt',
    'release_workflow_template.yml',
    'release_config.example.json',
    'DEVELOPMENT_STANDARD_KO.md',
    'ROADMAP_KO.md',
    'AI_SETUP_KO.txt',
    'update_manifest.example.json',
    'Setup_GitHub_AutoRelease.ps1',
    'Setup_GitHub_AutoRelease.bat',
    'GITHUB_AUTORELEASE_SETUP_KO.md'
)

$script:CurrentStep = '배포 파일 목록 검증'
# Ensure this script only exports an explicitly allowlisted source set; never copy local data/keys/backups.
foreach ($Name in $SourceFiles) { Get-CheckedText -Path (Join-Path $SourceRoot $Name) | Out-Null }
if (Test-Path -LiteralPath $WorkspacePath) {
    if ((Get-ChildItem -LiteralPath $WorkspacePath -Force -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {
        throw "작업 폴더가 이미 존재하고 비어 있지 않습니다. 기존 내용을 보호하기 위해 중단했습니다: $WorkspacePath"
    }
} else {
    New-Item -ItemType Directory -Path $WorkspacePath -Force | Out-Null
}

$script:CurrentStep = '필수 프로그램 점검'
Write-SetupLog ("작업 폴더: {0}" -f $WorkspacePath)
$RequiredPackages = [ordered]@{
    'git' = 'Git.Git'
    'gh' = 'GitHub.cli'
    'python' = 'Python.Python.3.13'
    'node' = 'OpenJS.NodeJS.LTS'
}
Refresh-SetupPath
$MissingCommands = @(Get-MissingSetupCommands)
if ($MissingCommands.Count -gt 0) {
    Write-Host ("필수 도구가 없습니다: {0}" -f ($MissingCommands -join ', ')) -ForegroundColor Yellow
    Write-SetupLog ("시작 시 누락된 도구: {0}" -f ($MissingCommands -join ', '))
    if ($SkipDependencyInstall) {
        throw ("새 PowerShell에서도 다음 도구를 찾을 수 없습니다: {0}. PC를 재시작한 뒤 다시 실행하거나 아래 경로/로그를 확인하세요." -f ($MissingCommands -join ', '))
    }
    if (Get-Command 'winget' -CommandType Application -ErrorAction SilentlyContinue) {
        Write-Host '필수 도구 설치가 끝난 다음 자동으로 새 PowerShell에서 설정을 이어갑니다.' -ForegroundColor Cyan
        Write-Host '설치가 진행되는 동안 창을 닫거나 아무 키나 누르지 마세요. 설치 후 GitHub 로그인 및 저장소 확인 질문이 이어집니다.' -ForegroundColor Cyan
        Write-Host '설치 도중 관리자 권한 또는 Windows 재시작이 필요한 경우 해당 Windows 안내를 따르세요.' -ForegroundColor Yellow
        Write-Host 'Windows 패키지 관리자 winget으로 위 도구를 설치할 수 있습니다. 설치는 이 PC에 프로그램을 추가합니다.' -ForegroundColor Yellow
        $InstallChoice = Read-Host '자동 설치를 시작하려면 INSTALL을 입력하세요'
        if ($InstallChoice -cne 'INSTALL') {
            throw ("필수 도구가 없어 중단했습니다: {0}. INSTALL을 선택하거나 도구를 직접 설치한 뒤 다시 실행하세요." -f ($MissingCommands -join ', '))
        }
        foreach ($MissingCommand in $MissingCommands) {
            Write-Host ("`n[{0}/{1}] {2} 설치를 시작합니다." -f ([array]::IndexOf([string[]]$MissingCommands, [string]$MissingCommand) + 1), $MissingCommands.Count, $MissingCommand) -ForegroundColor Cyan
            Invoke-CheckedCommand -Executable 'winget' -Arguments @('install', '--id', $RequiredPackages[$MissingCommand], '--exact', '--source', 'winget', '--accept-package-agreements', '--accept-source-agreements') -Step ("필수 도구 설치: {0}" -f $MissingCommand)
        }
        Refresh-SetupPath
        $StillMissing = @(Get-MissingSetupCommands)
        if ($StillMissing.Count -gt 0) {
            Write-SetupLog ("설치 완료 후 현재 프로세스에서 누락된 도구: {0}. 새 PowerShell에서 한 번 이어서 확인합니다." -f ($StillMissing -join ', '))
            Write-Host ("설치 프로그램이 PATH를 갱신했을 수 있어 새 PowerShell 창에서 설정을 이어갑니다. 남은 도구: {0}" -f ($StillMissing -join ', ')) -ForegroundColor Yellow
            $ResumeArguments = @(
                '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath,
                '-RepositoryName', $RepositoryName,
                '-Visibility', $Visibility,
                '-WorkspacePath', $WorkspacePath,
                '-LogPath', $LogPath,
                '-SkipDependencyInstall'
            )
            if ($NoWait) { $ResumeArguments += '-NoWait' }
            & powershell.exe @ResumeArguments
            $ResumeExitCode = $LASTEXITCODE
            if ($ResumeExitCode -ne 0) {
                Write-SetupLog ("새 PowerShell 이어서 실행 실패: 종료 코드 {0}" -f $ResumeExitCode)
                throw ("필수 도구 설치 뒤 새 PowerShell에서 설정을 이어가지 못했습니다. 종료 코드: {0}. 창에 표시된 원인과 로그를 확인하세요." -f $ResumeExitCode)
            }
            Write-SetupLog '새 PowerShell 프로세스에서 설정 이어서 실행이 정상 종료되었습니다.'
            exit 0
        }
        Write-Host '필수 도구 경로 확인 완료. GitHub 로그인 및 저장소 설정 단계로 이어갑니다.' -ForegroundColor Green
    } else {
        throw ("winget을 찾을 수 없으며 필수 도구가 없습니다: {0}. Git, GitHub CLI, Python 3, Node.js를 설치한 뒤 다시 실행하세요." -f ($MissingCommands -join ', '))
    }
}

# Use a browser-assisted GitHub CLI login when this PC has not been authenticated.
$script:CurrentStep = 'GitHub 로그인 확인'
& gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'GitHub CLI 로그인이 필요합니다. 브라우저 인증 창을 열겠습니다. 표시된 안내에 따라 본인 계정으로 로그인하세요.' -ForegroundColor Yellow
    Invoke-CheckedCommand -Executable 'gh' -Arguments @('auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https') -Step 'GitHub 브라우저 로그인'
}
Invoke-CheckedCommand -Executable 'gh' -Arguments @('auth', 'status') -Step 'GitHub 로그인 확인'
$Login = (& gh api user --jq '.login').Trim()
if ($LASTEXITCODE -ne 0 -or -not $Login) { throw 'GitHub 사용자 계정을 확인할 수 없습니다. gh auth login을 먼저 실행하세요.' }
$UserId = (& gh api user --jq '.id').Trim()
if ($LASTEXITCODE -ne 0 -or -not $UserId) { throw 'GitHub 계정 ID를 확인할 수 없습니다.' }
$script:CurrentStep = '저장소 또는 GitHub Projects 주소 입력'
# Accept a repository URL/name OR a GitHub Projects V2 board URL. Resolve linked issues/PRs locally via the user's authenticated gh CLI.
$DefaultRepositoryUrl = 'https://github.com/goldensw1130/-sw'
$RepositoryInput = Read-Host ("GitHub 저장소 이름, owner/repo, 저장소 URL 또는 Projects 보드 URL 입력 (기본값: {0})" -f $DefaultRepositoryUrl)
$RepositoryOwner = $Login
$InputValue = if ([string]::IsNullOrWhiteSpace($RepositoryInput)) { $DefaultRepositoryUrl } else { $RepositoryInput.Trim() }
if (-not [string]::IsNullOrWhiteSpace($InputValue) -and $InputValue -match '^https://github\.com/(users|orgs)/([A-Za-z0-9_.-]+)/projects/(\d+)(?:/views/\d+)?/?(?:\?.*)?$') {
    $ProjectOwnerKind = $Matches[1]
    $ProjectOwner = $Matches[2]
    $ProjectNumber = $Matches[3]
    $script:CurrentStep = 'GitHub Projects 보드 확인'
    Write-Host ("프로젝트 보드 주소를 확인했습니다: {0}, 프로젝트 번호 {1}" -f $ProjectOwner, $ProjectNumber) -ForegroundColor Cyan
    Write-SetupLog ("사용자가 Projects 보드 URL 입력: owner={0}; number={1}" -f $ProjectOwner, $ProjectNumber)
    if ($ProjectOwner -ine $Login) {
        Write-Warning ("보드 소유자({0})와 현재 gh 로그인({1})이 다릅니다. 다른 계정에 실수로 저장소를 만들지 않도록 확인이 필요합니다." -f $ProjectOwner, $Login)
        $AccountChoice = Read-Host '프로젝트 소유자 계정으로 전환하려면 SWITCH-ACCOUNT를 입력하세요. 현재 계정을 유지하려면 ENTER'
        if ($AccountChoice -ceq 'SWITCH-ACCOUNT') {
            & gh auth switch --hostname github.com --user $ProjectOwner 2>$null | Out-Null
            $SwitchExit = $LASTEXITCODE
            if ($SwitchExit -ne 0) {
                Write-Host '해당 계정이 CLI에 등록되어 있지 않습니다. 브라우저 로그인을 열어 계정을 추가합니다.' -ForegroundColor Yellow
                Invoke-CheckedCommand -Executable 'gh' -Arguments @('auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https') -Step 'Projects 보드 소유자 계정 로그인'
            }
            $Login = (& gh api user --jq '.login').Trim()
            if ($LASTEXITCODE -ne 0 -or -not $Login) { throw '계정 전환 후 GitHub 로그인을 확인할 수 없습니다.' }
            $UserId = (& gh api user --jq '.id').Trim()
            if ($LASTEXITCODE -ne 0 -or -not $UserId) { throw '계정 전환 후 GitHub 사용자 ID를 확인할 수 없습니다.' }
            if ($Login -ine $ProjectOwner) { throw ("계정 전환 후에도 로그인 계정이 보드 소유자와 다릅니다. 로그인={0}, 보드 소유자={1}. 저장소는 만들지 않았습니다." -f $Login, $ProjectOwner) }
            $RepositoryOwner = $Login
            Write-SetupLog ("GitHub 계정 전환 확인: {0}" -f $Login)
        } else {
            # Keep the project owner as the intended owner. If no linked existing repo is selected, creating under another login is blocked below.
            $RepositoryOwner = $ProjectOwner
        }
    } else {
        $RepositoryOwner = $Login
    }
    $ProjectViewJson = & gh project view $ProjectNumber --owner $ProjectOwner --format json 2>$null
    $ProjectViewExit = $LASTEXITCODE
    if ($ProjectViewExit -ne 0 -or -not $ProjectViewJson) {
        Write-Host 'Projects 보드 조회 권한이 없거나 project 권한 범위가 부족할 수 있습니다.' -ForegroundColor Yellow
        $ScopeChoice = Read-Host 'GitHub Projects 권한을 요청하려면 PROJECT-SCOPE를 입력하세요. 저장소를 직접 입력하려면 ENTER'
        if ($ScopeChoice -ceq 'PROJECT-SCOPE') {
            Invoke-CheckedCommand -Executable 'gh' -Arguments @('auth', 'refresh', '-s', 'project') -Step 'GitHub Projects 권한 갱신'
            $ProjectViewJson = & gh project view $ProjectNumber --owner $ProjectOwner --format json 2>$null
            $ProjectViewExit = $LASTEXITCODE
        }
    }
    if ($ProjectViewExit -eq 0 -and $ProjectViewJson) {
        Write-Host ("프로젝트 보드 접근 성공: {0}/projects/{1}" -f $ProjectOwner, $ProjectNumber) -ForegroundColor Green
        $ProjectItemsJson = & gh project item-list $ProjectNumber --owner $ProjectOwner --format json --limit 100 2>$null
        $ProjectItemsExit = $LASTEXITCODE
        $ProjectCandidates = @{}
        if ($ProjectItemsExit -eq 0 -and $ProjectItemsJson) {
            $ProjectItemsText = @($ProjectItemsJson) -join "`n"
            # Project item JSON can expose either web issue/PR URLs or a repository nameWithOwner string.
            $IssueUrlPattern = '(?i)https?://(?:api\.)?github\.com/(?:repos/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/(?:issues|pull)/\d+'
            foreach ($ProjectMatch in [regex]::Matches($ProjectItemsText, $IssueUrlPattern)) {
                $CandidateName = $ProjectMatch.Groups[1].Value + '/' + $ProjectMatch.Groups[2].Value
                if (-not $ProjectCandidates.ContainsKey($CandidateName)) { $ProjectCandidates[$CandidateName] = 0 }
                $ProjectCandidates[$CandidateName]++
            }
            $RepositoryFieldPattern = '(?i)"(?:repository|repositoryNameWithOwner|repositoryFullName|nameWithOwner)"\s*:\s*"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)"'
            foreach ($ProjectMatch in [regex]::Matches($ProjectItemsText, $RepositoryFieldPattern)) {
                $CandidateName = $ProjectMatch.Groups[1].Value + '/' + $ProjectMatch.Groups[2].Value
                if (-not $ProjectCandidates.ContainsKey($CandidateName)) { $ProjectCandidates[$CandidateName] = 0 }
                $ProjectCandidates[$CandidateName]++
            }
        } else {
            Write-Warning '프로젝트 항목 목록을 읽지 못했습니다. 이 보드에 연결된 저장소를 자동으로 찾지 못했으므로 저장소 주소를 직접 입력하세요.'
            Write-SetupLog 'Project item-list failed or empty; manual repository selection required.'
        }
        if ($ProjectCandidates.Count -eq 1) {
            $ProjectCandidateEntry = $ProjectCandidates.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 1
            $ProjectCandidate = [string]$ProjectCandidateEntry.Key
            Write-Host ("프로젝트 보드 카드에서 저장소 후보를 찾았습니다: {0}" -f $ProjectCandidate) -ForegroundColor Cyan
            $CandidateChoice = Read-Host '이 저장소를 대상으로 하려면 USE-PROJECT-REPO를 입력하세요. 다른 저장소/이름 입력 또는 ENTER는 별도 지정'
            if ($CandidateChoice -ceq 'USE-PROJECT-REPO') {
                $InputValue = $ProjectCandidate
            } else {
                $InputValue = [string]$CandidateChoice
            }
        } elseif ($ProjectCandidates.Count -gt 1) {
            Write-Host '프로젝트 보드에서 여러 연결 저장소를 찾았습니다. 숏폼 나침반 소스가 들어갈 저장소를 직접 선택하세요:' -ForegroundColor Yellow
            foreach ($CandidateName in ($ProjectCandidates.Keys | Sort-Object)) { Write-Host ('  - ' + $CandidateName) }
            $InputValue = Read-Host '대상 저장소의 owner/repo 또는 https://github.com/owner/repo 입력 (새 저장소 이름은 이름만 입력)'
        } else {
            Write-Host '프로젝트 보드에서 소스 저장소를 특정할 issue/PR 링크를 찾지 못했습니다. Projects 보드는 저장소와 별개이므로 대상 저장소를 따로 선택해야 합니다.' -ForegroundColor Yellow
            $InputValue = Read-Host ("실제 저장소 URL, owner/repo 또는 새 저장소 이름 입력 (빈칸은 기본값: {0})" -f $DefaultRepositoryUrl)
            if ([string]::IsNullOrWhiteSpace($InputValue)) { $InputValue = $DefaultRepositoryUrl }
        }
    } else {
        Write-Warning '프로젝트 보드는 현재 로그인으로 조회할 수 없습니다. 주소의 사용자/조직 이름과 `gh auth status`를 확인하세요.'
        $InputValue = Read-Host ("저장소 URL, owner/repo 또는 새 저장소 이름을 직접 입력 (빈칸은 기본값: {0})" -f $DefaultRepositoryUrl)
        if ([string]::IsNullOrWhiteSpace($InputValue)) { $InputValue = $DefaultRepositoryUrl }
        Write-SetupLog ("Project board access failed; user prompted for a repository manually. Owner={0}; login={1}" -f $ProjectOwner, $Login)
    }
}
if (-not [string]::IsNullOrWhiteSpace($InputValue)) {
    if ($InputValue -match '^https://github\.com/') {
        try { $InputUri = [uri]$InputValue } catch { throw 'GitHub URL을 해석할 수 없습니다.' }
        if ($InputUri.Scheme -ne 'https' -or $InputUri.Host -ne 'github.com') { throw 'GitHub 주소는 https://github.com/owner/repo 형식이어야 합니다.' }
        $UrlParts = @($InputUri.AbsolutePath.Trim('/').Split('/') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        if ($UrlParts.Count -ne 2) { throw '대상 URL이 저장소 루트가 아닙니다. 예: https://github.com/owner/repo . Projects 보드 URL은 프로젝트 조회 후 저장소를 별도 선택해야 합니다.' }
        $RepositoryOwner = $UrlParts[0]
        $RepositoryName = $UrlParts[1] -replace '\.git$', ''
    } elseif ($InputValue -match '^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$') {
        $RepositoryOwner = $Matches[1]
        $RepositoryName = $Matches[2]
    } else {
        $RepositoryName = $InputValue
    }
}
if ($RepositoryOwner -notmatch '^[A-Za-z0-9_.-]{1,100}$' -or $RepositoryName -notmatch '^[A-Za-z0-9_.-]{1,100}$') {
    throw '저장소는 이름, owner/repo 또는 https://github.com/owner/repo 형식으로 입력하세요. Projects 보드 URL을 입력하면 연결 항목을 조회한 뒤 저장소를 선택합니다.'
}
$FullRepository = "$RepositoryOwner/$RepositoryName"
if ($RepositoryOwner -ine $Login) {
    Write-Warning ("입력한 저장소 소유자({0})와 현재 gh 로그인({1})이 다릅니다." -f $RepositoryOwner, $Login)
    $AccountChoice = Read-Host ("소유자 {0}로 계정 전환을 시도하려면 SWITCH-ACCOUNT를 입력하세요. 이미 쓰기 권한이 있는 현재 계정을 유지하려면 ENTER" -f $RepositoryOwner)
    if ($AccountChoice -ceq 'SWITCH-ACCOUNT') {
        & gh auth switch --hostname github.com --user $RepositoryOwner 2>$null | Out-Null
        $SwitchExit = $LASTEXITCODE
        if ($SwitchExit -ne 0) {
            Write-Host '대상 계정이 CLI에 등록되어 있지 않습니다. 브라우저 인증을 시작합니다.' -ForegroundColor Yellow
            Invoke-CheckedCommand -Executable 'gh' -Arguments @('auth', 'login', '--hostname', 'github.com', '--web', '--git-protocol', 'https') -Step '저장소 소유자 계정 브라우저 로그인'
        }
        $Login = (& gh api user --jq '.login').Trim()
        if ($LASTEXITCODE -ne 0 -or -not $Login) { throw '계정 전환 후 GitHub 로그인 계정을 확인할 수 없습니다.' }
        $UserId = (& gh api user --jq '.id').Trim()
        if ($LASTEXITCODE -ne 0 -or -not $UserId) { throw '계정 전환 후 GitHub 사용자 ID를 확인할 수 없습니다.' }
        if ($Login -ine $RepositoryOwner) { throw ("계정 전환 후 로그인 계정이 저장소 소유자와 일치하지 않습니다. 로그인={0}; 저장소 소유자={1}. 원격 파일은 변경하지 않았습니다." -f $Login, $RepositoryOwner) }
        Write-SetupLog ("GitHub 계정 전환 확인: {0}" -f $Login)
    }
}
$script:CurrentStep = '기존 GitHub 저장소 확인'

# Reuse an existing repository only when it is empty or contains GitHub starter files.
# This avoids failing simply because the user created the repository first while protecting real project files.
$RemoteRepositoryExists = $false
$RemoteRepositoryInfo = $null
$RemoteRepositoryPaths = @()
$EffectiveVisibility = $Visibility
$RepoInfoJson = & gh api "repos/$FullRepository" --jq '{full_name:.full_name,owner:.owner.login,size:.size,default_branch:.default_branch,private:.private,can_push:.permissions.push}' 2>$null
$RepoInfoExit = $LASTEXITCODE
if ($RepoInfoExit -eq 0 -and $RepoInfoJson) {
    $RemoteRepositoryExists = $true
    try { $RemoteRepositoryInfo = ($RepoInfoJson | Out-String | ConvertFrom-Json) } catch { throw "GitHub 저장소 메타데이터를 읽을 수 없습니다: $FullRepository" }
    if ([string]$RemoteRepositoryInfo.owner -ine $RepositoryOwner) { throw 'GitHub가 반환한 저장소 소유자가 요청한 소유자와 다릅니다. 원격 저장소를 수정하지 않았습니다.' }
    if ($RepositoryOwner -ine $Login -and $RemoteRepositoryInfo.can_push -ne $true) {
        throw '로그인 계정에 해당 저장소의 쓰기 권한이 확인되지 않습니다. 해당 계정으로 로그인하거나 본인 계정의 저장소 URL을 입력하세요.'
    }
    $EffectiveVisibility = if ([bool]$RemoteRepositoryInfo.private) { 'Private' } else { 'Public' }
    if (-not [string]::IsNullOrWhiteSpace([string]$RemoteRepositoryInfo.default_branch)) {
        $EncodedBranch = [uri]::EscapeDataString([string]$RemoteRepositoryInfo.default_branch)
        # Avoid gh --jq string filters here: Windows PowerShell 5.1 can pass embedded
        # quotes to the native gh process inconsistently, which may turn "blob" into
        # an undefined jq function (blob/0). Read raw JSON and filter it in PowerShell.
        $TreeJson = & gh api "repos/$FullRepository/git/trees/$EncodedBranch`?recursive=1" 2>$null
        $TreeExit = $LASTEXITCODE
        if ($TreeExit -ne 0 -or -not $TreeJson) { throw '기존 저장소 파일 목록을 읽을 수 없습니다. 파일을 덮어쓰지 않고 중단했습니다.' }
        try {
            $TreeResponse = ($TreeJson | Out-String | ConvertFrom-Json -ErrorAction Stop)
            $RemoteRepositoryPaths = @($TreeResponse.tree | Where-Object { [string]$_.type -eq 'blob' } | ForEach-Object { [string]$_.path })
        } catch { throw '기존 저장소의 파일 목록을 해석할 수 없습니다.' }
        if ($RemoteRepositoryPaths -contains 'ShortCompassServer.py' -or $RemoteRepositoryPaths -contains 'ShortsCompass.html') {
            throw '기존 저장소에 숏폼 나침반 코드로 보이는 파일이 이미 있습니다. 자동 덮어쓰기를 차단했습니다. 전용 업데이트 절차로 병합해야 합니다.'
        }
        $StarterPattern = '^(README\.md|\.gitignore|\.gitattributes|LICENSE(\.(md|txt|rst))?|CODE_OF_CONDUCT\.md|CONTRIBUTING\.md|\.github/workflows/release\.yml)$'
        $UnexpectedPaths = @($RemoteRepositoryPaths | Where-Object { $_ -notmatch $StarterPattern })
        if ($UnexpectedPaths.Count -gt 0) {
            throw ("기존 저장소에 허용되지 않은 파일이 있어 자동 변경을 중단했습니다. 기존 파일은 유지했습니다: " + ($UnexpectedPaths -join ', '))
        }
    } elseif ([int]$RemoteRepositoryInfo.size -gt 0) {
        throw '기존 저장소가 비어 있지 않지만 기본 브랜치가 없어 파일 목록을 검증할 수 없습니다. 원격 내용을 보호하기 위해 중단했습니다.'
    }
    Write-Host ("이미 만든 GitHub 저장소를 안전 조건 확인 후 사용합니다: {0}" -f $FullRepository) -ForegroundColor Cyan
    Write-SetupLog ("기존 저장소 사용 후보: {0}; 크기={1}; 비공개={2}; 파일={3}" -f $FullRepository, $RemoteRepositoryInfo.size, $RemoteRepositoryInfo.private, ($RemoteRepositoryPaths -join ','))
} else {
    if ($RepositoryOwner -ine $Login) {
        throw ("저장소가 존재하지 않고 소유자가 로그인 계정과 다릅니다: {0}. 새 저장소는 현재 로그인 계정({1}) 아래에서 생성해야 합니다." -f $FullRepository, $Login)
    }
    Write-Host ("새 GitHub 저장소를 생성할 예정입니다: {0}" -f $FullRepository) -ForegroundColor Cyan
    Write-SetupLog ("저장소가 없어 신규 생성 예정: {0}" -f $FullRepository)
}

if ($RemoteRepositoryExists) {
    if ([bool]$RemoteRepositoryInfo.private) {
        Write-Warning '기존 저장소는 Private입니다. 현재 앱의 인증 없는 업데이트 클라이언트는 비공개 릴리스 자산을 내려받을 수 없습니다.'
    } else {
        Write-Warning '공개 저장소에는 허용 목록의 프로그램 소스와 문서가 누구나 볼 수 있게 됩니다. 실제 API 키, 사용자 데이터, 비공개 정보가 없어야 합니다.'
    }
    $Confirmation = Read-Host '기존 저장소가 비어 있거나 허용된 기본 파일과 release.yml만 있는지 확인했습니다. 계속하려면 USE-EXISTING을 입력하세요'
    if ($Confirmation -cne 'USE-EXISTING') { throw '사용자가 기존 저장소 연결을 취소했습니다. 변경하지 않았습니다.' }
    Invoke-CheckedCommand -Executable 'gh' -Arguments @('repo', 'clone', $FullRepository, $WorkspacePath) -Step '기존 저장소 로컬 복제'
} else {
    if ($Visibility -eq 'Public') {
        Write-Warning 'Public 저장소는 소스 코드와 릴리스 자산을 누구나 볼 수 있습니다. 실제 API 키, 사용자 데이터, 비공개 정보가 포함되지 않도록 확인하세요.'
    } else {
        Write-Warning 'Private 저장소로 만듭니다. 인증 없는 자동 업데이트는 별도 인증 피드 없이는 작동하지 않습니다.'
    }
    Write-Host ("GitHub에 새 {0} 저장소를 생성합니다: {1}" -f $Visibility, $FullRepository) -ForegroundColor Yellow
    Write-Host ("작업 폴더: {0}" -f $WorkspacePath) -ForegroundColor Yellow
    if ($Visibility -eq 'Public') { Write-Host '공개 저장소에서는 허용 목록에 포함된 프로그램 소스와 문서가 누구나 볼 수 있게 됩니다.' -ForegroundColor Yellow }
    $Confirmation = Read-Host '계속하려면 CREATE를 입력하세요'
    if ($Confirmation -cne 'CREATE') { throw '사용자가 원격 저장소 생성을 취소했습니다. 원격 저장소는 생성하지 않았습니다.' }
}

# Copy only named project files; preserve existing GitHub starter README and ignore rules.
foreach ($Name in $SourceFiles) {
    Copy-Item -LiteralPath (Join-Path $SourceRoot $Name) -Destination (Join-Path $WorkspacePath $Name) -Force
}

$WorkflowDirectory = Join-Path $WorkspacePath '.github/workflows'
New-Item -ItemType Directory -Path $WorkflowDirectory -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $WorkspacePath 'release_workflow_template.yml') -Destination (Join-Path $WorkflowDirectory 'release.yml') -Force

$GitIgnorePath = Join-Path $WorkspacePath '.gitignore'
$RequiredIgnoreLines = @('__pycache__/', '*.py[cod]', '.venv/', 'venv/', 'dist/', '.env', '.env.*', '*.log', 'shortcompass_data.json', 'shortcompass_state.json', 'release_config.json', '*_backup_*.json', 'ShortsCompass-backup-*.json')
if (Test-Path -LiteralPath $GitIgnorePath -PathType Leaf) {
    $ExistingIgnoreLines = @([System.IO.File]::ReadAllLines($GitIgnorePath, [System.Text.Encoding]::UTF8))
    $CombinedIgnoreLines = New-Object System.Collections.Generic.List[string]
    foreach ($Line in $ExistingIgnoreLines) { $CombinedIgnoreLines.Add($Line) }
    foreach ($Line in $RequiredIgnoreLines) { if ($ExistingIgnoreLines -notcontains $Line) { $CombinedIgnoreLines.Add($Line) } }
    [System.IO.File]::WriteAllText($GitIgnorePath, ($CombinedIgnoreLines -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
} else {
    [System.IO.File]::WriteAllText($GitIgnorePath, ($RequiredIgnoreLines -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
}

$Readme = @'
# 숏폼 나침반

자동 릴리스 저장소입니다. 앱 소스 버전은 %VERSION%이며 GitHub Actions가 태그 %TAG%를 받아 테스트 후 릴리스 ZIP, 업데이트 manifest, SHA-256 파일을 게시합니다.

## 새 버전 배포

1. 소스 코드를 수정하고 ShortCompassServer.py의 APP_VERSION, HTML 제목/하단/백업 버전과 릴리스 노트를 동일하게 맞춥니다.
2. Python 및 JavaScript 회귀 테스트를 실행합니다.
3. 커밋 후 해당 커밋에서 새 버전 태그를 만들고 푸시합니다. 예: git tag %TAG% 및 git push origin %TAG%.
4. Actions 실행이 통과하면 GitHub Releases에 ZIP, update_manifest.json, SHA256SUMS.txt가 게시됩니다.

업데이트 manifest: %MANIFEST_URL%

이 저장소가 Private이면 인증 없는 앱 업데이트 클라이언트는 릴리스 자산에 접근할 수 없습니다.
'@
$Readme = $Readme.Replace('%VERSION%', $Version).Replace('%TAG%', $Tag).Replace('%MANIFEST_URL%', "https://github.com/$FullRepository/releases/latest/download/update_manifest.json")
$ReadmePath = Join-Path $WorkspacePath 'README.md'
if (Test-Path -LiteralPath $ReadmePath -PathType Leaf) {
    $ExistingReadme = [System.IO.File]::ReadAllText($ReadmePath, [System.Text.Encoding]::UTF8)
    if (-not [string]::IsNullOrWhiteSpace($ExistingReadme)) {
        $GuidePath = Join-Path $WorkspacePath 'SHORTCOMPASS_RELEASE_GUIDE.md'
        [System.IO.File]::WriteAllText($GuidePath, $Readme + "`n", [System.Text.UTF8Encoding]::new($false))
        Write-SetupLog '기존 README.md를 보존하고 SHORTCOMPASS_RELEASE_GUIDE.md에 자동 릴리스 안내를 기록했습니다.'
    } else {
        [System.IO.File]::WriteAllText($ReadmePath, $Readme + "`n", [System.Text.UTF8Encoding]::new($false))
    }
} else {
    [System.IO.File]::WriteAllText($ReadmePath, $Readme + "`n", [System.Text.UTF8Encoding]::new($false))
}

# Fail closed on common credential/private-key patterns across every file that will be committed.
$SecretPatterns = @(
    @{ Name = 'OpenAI-like API key'; Pattern = '\bsk-[A-Za-z0-9_-]{32,}\b' },
    @{ Name = 'Anthropic-like API key'; Pattern = '\bsk-ant-[A-Za-z0-9_-]{24,}\b' },
    @{ Name = 'Google API key'; Pattern = '\bAIza[0-9A-Za-z_-]{35}\b' },
    @{ Name = 'private key header'; Pattern = '-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----' }
)
$Findings = @()
$FilesToScan = @($SourceFiles) + @('.gitignore', 'SHORTCOMPASS_RELEASE_GUIDE.md', 'README.md', '.github/workflows/release.yml')
$FilesToScan = @($FilesToScan | Select-Object -Unique | Where-Object { Test-Path -LiteralPath (Join-Path $WorkspacePath $_) -PathType Leaf })
foreach ($Name in $FilesToScan) {
    $Text = [System.IO.File]::ReadAllText((Join-Path $WorkspacePath $Name), [System.Text.Encoding]::UTF8)
    foreach ($Rule in $SecretPatterns) {
        if ([regex]::IsMatch($Text, $Rule.Pattern)) {
            $Findings += "$Name ($($Rule.Name))"
            break
        }
    }
}
if ($Findings.Count -gt 0) {
    throw ("잠재적 비밀정보 패턴을 발견해 GitHub 업로드를 차단했습니다: " + ($Findings -join ', ') + '. 실제 키가 아닌 테스트 패턴이어도 직접 확인하세요.')
}

Push-Location $WorkspacePath
try {
    Invoke-CheckedCommand -Executable 'python' -Arguments @('-m', 'unittest', 'Test_ShortCompass.py', 'Test_UpdateAndAI.py', 'Test_ReleaseTools.py', 'Test_GitHubBootstrap.py', '-v') -Step 'Python 회귀 테스트'
    Invoke-CheckedCommand -Executable 'node' -Arguments @('Test_ABReliability.js') -Step 'A/B 실험 테스트'
    Invoke-CheckedCommand -Executable 'node' -Arguments @('Test_OpportunityLearning.js') -Step '성과 학습 테스트'
    Invoke-CheckedCommand -Executable 'node' -Arguments @('Test_YouTubeRanking.js') -Step 'YouTube 정렬 테스트'
    Invoke-CheckedCommand -Executable 'node' -Arguments @('Test_UpdateUI.js') -Step '업데이트 UI 테스트'
    Invoke-CheckedCommand -Executable 'node' -Arguments @('Test_FullDiagnosticsUI.js') -Step '전체 진단 UI 테스트'

    $PreflightOutput = Join-Path $env:TEMP ("ShortCompass-Release-Preflight-" + [guid]::NewGuid().ToString('N'))
    try {
        Invoke-CheckedCommand -Executable 'python' -Arguments @('Prepare_Release.py', '--version', $Version, '--repository', $FullRepository, '--minimum-version', '2.38', '--output', $PreflightOutput, '--notes-file', 'RELEASE_NOTES_CURRENT_KO.txt') -Step '릴리스 ZIP/manifest 사전 검증'
    } finally {
        if (Test-Path -LiteralPath $PreflightOutput) { Remove-Item -LiteralPath $PreflightOutput -Recurse -Force }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $WorkspacePath '.git') -PathType Container)) {
        Invoke-CheckedCommand -Executable 'git' -Arguments @('init', '-b', 'main') -Step '로컬 Git 저장소 초기화'
    } else {
        $CurrentBranch = (& git branch --show-current).Trim()
        if ($LASTEXITCODE -ne 0) { throw '기존 저장소의 Git 브랜치를 확인할 수 없습니다.' }
        if ([string]::IsNullOrWhiteSpace($CurrentBranch)) {
            Invoke-CheckedCommand -Executable 'git' -Arguments @('checkout', '-b', 'main') -Step '빈 원격 저장소의 main 브랜치 생성'
        }
    }
    Invoke-CheckedCommand -Executable 'git' -Arguments @('config', 'user.name', 'ShortCompass Release Bootstrap') -Step 'Git 커밋 작성자 설정'
    Invoke-CheckedCommand -Executable 'git' -Arguments @('config', 'user.email', "$UserId+$Login@users.noreply.github.com") -Step 'Git 커밋 이메일 설정'
    Invoke-CheckedCommand -Executable 'git' -Arguments @('add', '--all') -Step '소스 스테이징'
    Invoke-CheckedCommand -Executable 'git' -Arguments @('diff', '--cached', '--check') -Step '공백/패치 오류 검사'
    Invoke-CheckedCommand -Executable 'git' -Arguments @('commit', '-m', "Initialize ShortCompass v$Version auto-release pipeline") -Step '초기 커밋 생성'

    if ($RemoteRepositoryExists) {
        $PushBranch = (& git branch --show-current).Trim()
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($PushBranch)) { throw '푸시할 Git 브랜치를 확인할 수 없습니다.' }
        Invoke-CheckedCommand -Executable 'git' -Arguments @('push', 'origin', $PushBranch) -Step '기존 GitHub 저장소에 소스 푸시'
    } else {
        $VisibilityFlag = if ($Visibility -eq 'Public') { '--public' } else { '--private' }
        $CreateArguments = @('repo', 'create', $FullRepository, $VisibilityFlag, '--source', $WorkspacePath, '--remote', 'origin', '--push', '--description', 'ShortCompass desktop app and verified automatic releases')
        Invoke-CheckedCommand -Executable 'gh' -Arguments $CreateArguments -Step '전용 GitHub 저장소 생성 및 main 푸시'
    }

    # Refuse to replace any existing release tag.
    & gh api "repos/$FullRepository/git/ref/tags/$Tag" --jq '.ref' 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { throw "GitHub에 $Tag 태그가 이미 있습니다. 기존 릴리스를 덮어쓰지 않았습니다." }
    Invoke-CheckedCommand -Executable 'git' -Arguments @('tag', '-a', $Tag, '-m', "ShortCompass $Tag initial release") -Step '초기 버전 태그 생성'
    Invoke-CheckedCommand -Executable 'git' -Arguments @('push', 'origin', "refs/tags/$Tag") -Step '초기 버전 태그 푸시'
} finally {
    Pop-Location
}

$RepositoryUrl = "https://github.com/$FullRepository"
$ManifestUrl = "$RepositoryUrl/releases/latest/download/update_manifest.json"
Write-Host "`n저장소: $RepositoryUrl" -ForegroundColor Cyan
Write-Host "작업 폴더: $WorkspacePath" -ForegroundColor Cyan
Write-Host "태그: $Tag" -ForegroundColor Cyan
Write-Host "업데이트 manifest: $ManifestUrl" -ForegroundColor Cyan

if (-not $NoWait) {
    $Deadline = (Get-Date).AddMinutes(10)
    $Completed = $false
    while ((Get-Date) -lt $Deadline) {
        $RunJson = & gh run list --repo $FullRepository --workflow 'release.yml' --limit 10 --json status,conclusion,url,headBranch 2>$null
        if ($LASTEXITCODE -eq 0 -and $RunJson) {
            try { $Runs = @($RunJson | ConvertFrom-Json) } catch { $Runs = @() }
            $MatchingRun = @($Runs | Where-Object { $_.headBranch -eq $Tag } | Select-Object -First 1)
            if ($MatchingRun.Count -gt 0) {
                $Run = $MatchingRun[0]
                Write-Host ("GitHub Actions 상태: {0} / {1} — {2}" -f $Run.status, $Run.conclusion, $Run.url) -ForegroundColor Yellow
                if ($Run.status -eq 'completed') {
                    if ($Run.conclusion -ne 'success') {
                        throw "GitHub Actions 릴리스 작업이 실패했습니다. 로그: $($Run.url) . 작업 폴더는 보존했습니다."
                    }
                    $Completed = $true
                    break
                }
            }
        }
        Start-Sleep -Seconds 10
    }
    if (-not $Completed) {
        Write-Warning '10분 안에 릴리스가 완료되지 않았습니다. GitHub Actions에서 release.yml 실행을 확인하세요.'
    } else {
        Write-Host "`n초기 릴리스 준비가 완료됐습니다: $RepositoryUrl/releases/tag/$Tag" -ForegroundColor Green
        if ($EffectiveVisibility -eq 'Private') {
            Write-Warning '비공개 저장소에서는 앱의 인증 없는 자동 업데이트가 작동하지 않습니다. 공개 배포를 선택하거나 비공개 피드 인증 기능을 별도로 설정해야 합니다.'
        } else {
            Register-UpdateFeedForCurrentUser -ManifestUrl $ManifestUrl
        }
    }
}

Write-SetupLog ("완료: 저장소 {0}, 태그 {1}" -f $FullRepository, $Tag)
Write-Host 'API 키나 토큰을 저장/출력하지 않았습니다. 이후 버전은 작업 폴더에서 변경사항을 커밋하고 새 vX.Y 태그를 푸시하면 자동 릴리스됩니다.'
Write-Host ("진단 로그: {0}" -f $LogPath) -ForegroundColor DarkGray
} catch {
    $FailureMessage = [string]$_.Exception.Message
    Write-Host ''
    Write-Host ("설정 실패 단계: {0}" -f $script:CurrentStep) -ForegroundColor Red
    Write-Host ("원인: {0}" -f $FailureMessage) -ForegroundColor Red
    Write-Host ("로그 파일: {0}" -f $LogPath) -ForegroundColor Yellow
    Write-SetupLog ("실패 단계: {0}" -f $script:CurrentStep)
    Write-SetupLog ("실패 원인: {0}" -f $FailureMessage)
    Write-SetupLog '기존 파일/저장소는 안전상 자동 삭제하지 않았습니다.'
    exit 1
}
