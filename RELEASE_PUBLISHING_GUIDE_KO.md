# 숏폼 나침반 자동 릴리스 운영 가이드 (v2.47)

## 현재 GitHub 저장소

- 저장소: https://github.com/goldensw1130/-sw
- 공개 Releases/업데이트 manifest: `https://github.com/goldensw1130/-sw/releases/latest/download/update_manifest.json`
- 저장소에는 tag 기반 `.github/workflows/release.yml`과 최초 설정 안내 README를 먼저 등록했습니다. 앱 소스와 v2.47 태그는 Windows 최초 설정 스크립트가 검사 후 푸시합니다.

## 최초 설정 1회

1. 이 ZIP 파일을 새 폴더에 압축 해제합니다.
2. `Setup_GitHub_AutoRelease.bat`을 더블클릭합니다.
3. 저장소 입력 질문에서 Enter를 누르면 `https://github.com/goldensw1130/-sw`가 기본 선택됩니다.
4. `gh auth` 계정이 `goldensw1130`이 아니면 `SWITCH-ACCOUNT`를 입력하고 브라우저에서 본인 계정 인증을 마칩니다.
5. 기존 저장소 확인에는 `USE-EXISTING`을 입력합니다. `CREATE`는 입력하지 마세요.
6. 스크립트는 별도의 날짜/시간 작업 폴더를 생성한 뒤 테스트, 공개 전 비밀정보 패턴 검사, ZIP/manifest 사전 검증을 실행합니다. 통과할 때만 `main`을 업데이트하고 `v2.47` 태그를 푸시합니다.

## 릴리스 이후 자동 동작

- GitHub Actions는 `v*` 태그 푸시로 시작합니다.
- 태그와 `ShortCompassServer.py`의 `APP_VERSION`이 일치해야 합니다.
- Python 회귀 테스트와 JavaScript 실행 테스트가 모두 통과해야 합니다.
- `Prepare_Release.py`가 저장소 고유 manifest URL이 삽입된 `ShortCompass-v2.47.zip`, `update_manifest.json`, `SHA256SUMS.txt`를 생성합니다.
- 모든 검사에 통과한 경우 GitHub Release에 세 파일을 게시합니다. 설치된 앱은 공개 manifest를 주기적으로 확인합니다. 업데이트 ZIP 적용은 앱에서 사용자가 승인해야 합니다.

## 후속 버전 게시

개발용 작업 폴더는 `%USERPROFILE%\ShortCompass-ReleaseRepo-날짜시간` 아래에 유지됩니다. 다음 버전에서 `APP_VERSION`, HTML 제목/하단/백업 메타데이터, 릴리스 노트를 같은 버전으로 바꾸고 테스트를 통과시킨 뒤 예를 들어 `v2.47`를 푸시합니다.

```powershell
git add .
git diff --cached --check
git commit -m "ShortCompass v2.47"
git push origin main
git tag v2.47
git push origin v2.47
```

같은 릴리스 태그는 재사용하지 않습니다. 기존 태그가 있으면 설정 스크립트는 덮어쓰지 않고 중단합니다.

## 오류 복구

설정 창에서 실패하면 오류 단계와 원인이 화면에 표시됩니다. 로그 위치는 `%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`입니다. 이전 작업 폴더는 자동 삭제하지 않으며, 재실행 때는 새 고유 경로를 사용합니다. 로그를 공유할 때 API 키나 인증 토큰이 있으면 보내지 마세요.

## 보안·정책 한계

- 공개 저장소에서는 소스와 릴리스가 누구나 읽을 수 있습니다. 실제 키, 사용자 자료, 비공개 문서를 올리지 마세요.
- 자동화된 비밀정보 패턴 검사와 SHA-256은 보조 안전장치이며, 모든 보안 위험을 검출하거나 배포자의 신원을 보증하지 않습니다.
- 플랫폼 정책 준수, 저작권 면책, 영상의 도달 또는 수익화를 보장하지 않습니다.
- GitHub Actions가 실행되려면 저장소의 Actions 설정에서 워크플로 실행이 차단되어 있지 않아야 합니다.


## v2.47 Windows 시작 안정화

시작 배치 파일은 서버를 별도 콘솔에서 실행하고 `/health` 정상 응답을 확인한 뒤 브라우저를 엽니다. 실패 로그는 `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`에 있습니다. 업데이트 허용 목록과 자동 릴리스 소스 목록에는 `Start_ShortCompass_Server.bat`이 포함됩니다.


## v2.47 Windows BAT 줄바꿈

배포 ZIP 내부 `.bat` 파일은 CRLF 줄바꿈으로 정규화됩니다. `Test_ReleaseTools.py`가 ZIP 안의 모든 배치 파일에서 CRLF 사용과 BOM 부재를 검사합니다.
