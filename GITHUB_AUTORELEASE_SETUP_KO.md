# 숏폼 나침반 GitHub 자동 릴리스 최초 설정 (v2.45)

## 먼저 확인한 한계

ChatGPT의 현재 GitHub 연결에서는 사용자가 새로 만든 숏폼 나침반 저장소를 확인할 수 없을 수 있습니다. 이 설정 스크립트는 사용자의 Windows PC에서 본인 GitHub CLI로 실행되므로, 저장소 이름·`owner/repo` 또는 GitHub URL을 입력해 기존 저장소를 연결할 수 있습니다. 기존 저장소의 내용을 자동 삭제하거나 다른 프로젝트 파일을 덮어쓰지 않습니다. 이 대화에서 자동으로 원격 저장소를 수정할 수 없는 경우에도, 스크립트가 PC에서 명시적 확인을 받은 뒤 초기 커밋과 릴리스를 진행하도록 구성되어 있습니다.

## GitHub Projects 보드 URL로 설정을 시작하기 (v2.45)

예를 들어 `https://github.com/users/계정명/projects/1/views/1` 같은 주소는 저장소 URL이 아니라 Projects V2 보드 주소입니다. v2.45부터 이 주소를 입력하면 스크립트가 `gh project view`와 `gh project item-list`로 보드를 조회하고, 보드에 들어 있는 이슈/PR을 통해 연결 저장소 후보를 찾습니다. 후보가 하나면 `USE-PROJECT-REPO` 입력으로 사용을 확인하며, 여러 후보면 `owner/repo`를 직접 고르게 합니다.

보드가 비어 있거나 이슈/PR이 연결되지 않았으면 보드만으로 소스 저장소를 알 수 없습니다. 이 경우 스크립트가 저장소 URL/`owner/repo`를 다시 요청합니다. 새 저장소를 만들려면 이름만 입력해도 됩니다. 기본 대상 저장소는 `https://github.com/goldensw1130/-sw`입니다. 대상 소유자와 gh 로그인 계정이 다르면 `SWITCH-ACCOUNT`로 계정을 전환할 수 있으며, 전환 후 계정명이 확인되지 않으면 중단합니다. 현재 `gh auth status`로 확인되는 계정은 보드 소유자에 접근할 수 있어야 하며, Projects 권한 범위가 부족하면 `PROJECT-SCOPE`를 입력해 `gh auth refresh -s project` 승인을 진행합니다. 전환이 확인되지 않으면 그 계정 아래에 새 저장소를 만들지 않습니다. 권한이 없는 계정이나 다른 사용자의 저장소를 우회하지 않습니다.

주의: GitHub 연결 플러그인 계정과 Windows PC의 `gh` 로그인 계정은 다를 수 있습니다. 이 스크립트는 Windows PC에서 로그인한 계정으로 실행됩니다. 화면의 계정 이름이 예상과 다르면 `gh auth status`를 먼저 확인하세요.

## 대상 저장소가 이미 만들어진 경우 (v2.45)

이번 프로젝트의 기본 대상 저장소는 `https://github.com/goldensw1130/-sw`입니다. 입력 프롬프트에서 Enter를 누르면 이 저장소를 대상으로 합니다. GitHub CLI 로그인 계정이 `goldensw1130`이 아니면 `SWITCH-ACCOUNT`를 입력해 대상 계정으로 전환하고, 브라우저 인증을 마친 뒤 다시 확인합니다. 저장소가 비어 있거나 `.github/workflows/release.yml` 하나만 있는 경우 `USE-EXISTING`을 입력하면 기존 워크플로를 최신 템플릿으로 바꾸고 프로그램 파일을 추가합니다. 다른 소스 파일이 있으면 덮어쓰지 않고 중단합니다.

기존 실행에서 남은 `$HOME\ShortCompass-ReleaseRepo` 폴더는 삭제하지 마세요. v2.45은 날짜/시간이 붙은 새 작업 폴더를 만들어 재시도합니다. 로그 경로는 `%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`입니다.

## 준비물

- Windows PowerShell
- Git
- GitHub CLI (`gh`)
- Python 3.11 이상 권장
- Node.js 24 이상 권장
- GitHub CLI에서 한 번 실행한 `gh auth login`

## v2.40에서 더블클릭 후 창이 닫혔을 때 (v2.45 수정)

v2.40 스크립트는 대상 저장소가 이미 있으면 무조건 중단했습니다. 사용자가 GitHub 화면에서 저장소를 먼저 만든 경우 이 검사에서 종료될 수 있습니다. v2.45은 저장소 이름·owner/repo·GitHub 저장소 URL을 실행 중 입력하고, 비어 있거나 README/.gitignore 등 기본 파일만 있는 저장소는 `USE-EXISTING` 확인 뒤 재사용합니다. README는 보존합니다. 다른 프로그램 파일이나 숏폼 나침반 코드가 이미 있으면 안전을 위해 자동으로 덮어쓰지 않습니다.

오류 로그는 `%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`에 저장됩니다. 이 파일에는 단계와 오류 원인만 기록하며 API 키/토큰은 기록하지 않습니다.

## 한 번만 실행하기

1. 이 안내서가 포함된 숏폼 나침반 v2.45 ZIP을 새 폴더에 압축 해제합니다. 이전 v2.40 폴더에서 스크립트 파일만 교체하지 말고 새 폴더에서 실행하세요.
2. 프로그램 소스 공개 여부를 결정합니다. 자동 업데이트 클라이언트가 로그인 없이 릴리스를 받으려면 저장소가 Public이어야 합니다.
3. 필요한 도구가 없으면 설정 스크립트가 winget 설치를 제안합니다. GitHub CLI 로그인이 안 되어 있으면 본인 계정으로 브라우저 인증을 진행합니다. 이 인증은 사용자가 직접 승인해야 하며, 스크립트에 토큰을 입력하거나 저장하지 않습니다.
4. 압축을 푼 폴더에서 `Setup_GitHub_AutoRelease.bat`을 더블클릭합니다. 또는 PowerShell에서 다음을 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\Setup_GitHub_AutoRelease.ps1
```

Public이 기본값입니다. 스크립트는 먼저 저장소 이름을 묻습니다(기본 `https://github.com/goldensw1130/-sw`는 Enter). 저장소 입력에는 이름(예: `my-shortcompass`), `owner/repo`, 또는 `https://github.com/owner/repo`를 사용할 수 있습니다. 저장소가 있으면 기본 파일과 릴리스 워크플로 외에 다른 코드가 없는지 확인한 뒤 `USE-EXISTING`, 없으면 공개 경고 뒤 `CREATE`를 입력해야 진행합니다. 공개를 원하지 않으면 취소하세요. 기존 README는 보존하고 다른 프로젝트 파일은 덮어쓰지 않습니다.

Private 저장소를 원한다면 다음을 실행할 수 있지만, 현재 앱의 인증 없는 업데이트 클라이언트는 Private 릴리스 자산을 다운로드하지 못합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\Setup_GitHub_AutoRelease.ps1 -Visibility Private
```

스크립트는 입력한 저장소 주소를 확인합니다. 다른 계정/조직의 기존 저장소는 인증 계정의 쓰기 권한이 확인되어야 재사용할 수 있으며, 새 저장소는 로그인한 계정 아래에서만 생성합니다. 기존 저장소가 비어 있거나 GitHub 기본 파일만 있으면 연결하고, 다른 프로그램 파일이 있으면 중단합니다. 이름은 실행할 때 입력하거나 `-RepositoryName my-shortcompass`로 지정할 수 있습니다. 작업 폴더는 기본적으로 `$HOME\ShortCompass-ReleaseRepo-날짜시간` 형태의 새 경로에 만듭니다. 이전 실패 작업 폴더가 남아 있어도 이를 덮어쓰거나 지우지 않고 새 작업 폴더로 다시 시도합니다.

## 무엇을 자동으로 수행하나

- 명시적으로 허용한 소스·테스트·문서 파일만 복사합니다. 임의 백업, 로컬 설정, 캐시, 로그는 복사하지 않습니다.
- 알려진 API 키 및 개인키 패턴을 검사합니다. 이 검사는 보조 수단이므로 사용자가 소스 공개 여부와 파일을 최종 검토해야 합니다.
- Python/JavaScript 회귀 테스트, ZIP·manifest 사전 검증, `git diff --cached --check`를 실행합니다.
- GitHub에 새 저장소를 만들고 `main`을 푸시한 뒤 `v2.45` 태그를 푸시합니다.
- GitHub Actions가 태그/소스 버전을 확인하고 테스트를 다시 실행한 다음 `ShortCompass-v2.45.zip`, `update_manifest.json`, `SHA256SUMS.txt`를 릴리스에 게시합니다. ZIP 안에는 빌드 대상 저장소의 실제 공개 manifest 주소가 기본 업데이트 피드로 포함됩니다.
- 첫 릴리스가 성공하면 이 Windows 사용자 계정의 `%LOCALAPPDATA%\ShortCompass\update_settings.json`에도 manifest 주소를 등록합니다. 기존에 다른 피드 URL이 설정되어 있으면 덮어쓰지 않고 경고만 표시합니다. 새로 설치한 공개 릴리스 ZIP도 저장소 주소가 기본 피드로 빌드되며, 이전 버전에 남아 있는 빈 피드 설정은 업데이트 확인이 켜져 있을 때 새 기본 주소로 자동 이전됩니다. 자동 확인 자체를 사용하지 않으려면 업데이트 센터에서 자동 확인을 끄세요.
- 기본적으로 GitHub 로그인 토큰을 스크립트나 소스 파일에 기록하지 않습니다.

## 공개/비공개 저장소 선택

기본값은 Public입니다. 그래야 현재 앱의 인증 없는 업데이트 클라이언트가 `update_manifest.json`과 ZIP 릴리스 자산을 읽을 수 있습니다. 그 대신 허용 목록에 포함된 소스 코드와 문서가 공개됩니다. 스크립트는 이 점을 표시하고 `CREATE` 입력을 요구하며, 사용자가 승인하기 전에는 원격 저장소를 만들지 않습니다.

소스를 공개하고 싶지 않다면 `-Visibility Private`을 사용할 수 있습니다. 이 경우 GitHub Actions 릴리스는 가능하지만 인증 없는 앱 자동 업데이트는 작동하지 않습니다. Private 저장소의 릴리스 자산을 배포하려면 별도의 인증 프록시/피드 설계가 필요합니다.

## 다음 버전 릴리스

작업 폴더 `$HOME\ShortCompass-ReleaseRepo-날짜시간`는 개발용 Git 저장소로 유지됩니다. 다음 버전부터는 서버 `APP_VERSION`, HTML의 제목/하단/백업 버전, 릴리스 노트를 동일하게 맞추고 테스트를 통과한 뒤 새 태그를 푸시합니다. 예를 들어 v2.45이면 `git tag v2.45`와 `git push origin v2.45`입니다. GitHub Actions가 검증 실패 시 릴리스를 중단합니다.

## 스크립트가 실패하면

창이 너무 빨리 닫히거나 아무 동작도 하지 않는 것처럼 보이면, 새 v2.45 ZIP의 `Setup_GitHub_AutoRelease.bat`을 사용하세요. 실패 단계와 원인을 화면에 표시하고 로그를 남깁니다. 로그는 `%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`에 있습니다. 도구 설치가 필요하면 `INSTALL`, 기존 저장소를 연결하려면 `USE-EXISTING`, 새 저장소 생성에는 `CREATE`를 직접 입력해야 진행합니다.

스크립트는 생성된 작업 폴더를 삭제하지 않습니다. 실패 단계와 원인을 `%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`에서 확인하세요. 기존 저장소에 README 외의 파일이 있다면 자동으로 덮어쓰지 않고 중단됩니다. 그 경우 파일 목록과 저장소 URL을 확인한 뒤 별도 병합 절차가 필요합니다. GitHub 저장소 생성 이후 실패했다면 같은 이름으로 다시 실행하지 말고 작업 폴더의 `git remote -v`, GitHub Actions 실행, Releases 페이지를 먼저 확인하세요.


## v2.45 설치가 끝난 뒤 저장소 질문이 나오지 않을 때

v2.45는 Git, GitHub CLI, Python, Node.js 설치 동의를 먼저 요청합니다. 설치가 끝나면 PATH를 갱신하고, 필요하면 새 PowerShell 프로세스에서 자동으로 나머지 설정을 이어갑니다. 새 프로세스에서도 도구를 찾지 못하면 해당 명령 이름과 로그 경로를 표시하고 멈춥니다. 로그 경로: `%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`.


## v2.45 설정 창이 바로 닫히는 문제 수정

v2.45의 `Setup_GitHub_AutoRelease.bat`은 동일 콘솔을 `cmd /k`로 유지합니다. PowerShell이 구문 오류나 실행 오류로 즉시 종료되어도 창과 로그 출력이 남습니다. 설치가 이미 완료됐다면 `INSTALL`을 다시 입력하지 마세요. 화면에 표시된 오류를 먼저 읽거나 다음 로그를 확인하세요.

`%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`


## v2.47 Windows 앱 실행 안정화

`Start_ShortCompass.bat`은 별도 `Start_ShortCompass_Server.bat` 서버 콘솔을 열고 `/health`가 v2.47 정상 응답을 반환한 다음 브라우저를 엽니다. 시작이 실패하면 창을 닫지 않고 로그 경로와 마지막 오류를 표시합니다. 실행 로그는 `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`에 기록됩니다. 이미 이전 버전 서버가 8765 포트에서 실행 중이면 이전 서버 창에서 `Ctrl+C`로 종료하고 새 실행 파일을 다시 여세요.


## v2.47 Windows BAT 실행 수정

릴리스 ZIP 생성기는 모든 `.bat` 파일을 CRLF 줄바꿈으로 정규화하고 회귀 테스트로 검사합니다. `Start_ShortCompass.bat`은 복잡한 FOR /F 명령 치환을 제거하고 서버의 `/health` 정상 응답 후 브라우저를 엽니다. 시작 실패 로그는 `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`입니다.
