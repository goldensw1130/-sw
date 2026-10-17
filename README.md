# 숏폼 나침반

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구 및 자동 릴리스 저장소입니다.

## 현재 상태

- 기본 저장소: https://github.com/goldensw1130/-sw
- GitHub Actions의 태그 기반 릴리스 워크플로가 준비되어 있습니다.
- 앱 소스와 첫 릴리스는 아직 게시되지 않았습니다. 첫 실행은 Windows용 v2.44 부트스트랩 ZIP에서 진행해야 합니다.

## 최초 설정 (v2.44)

1. [최신 설치 설정 복구판](https://github.com/goldensw1130/-sw/releases) 또는 ChatGPT에서 제공한 **숏폼 나침반 v2.44 설치 후 자동 진행 ZIP**을 새 폴더에 압축 해제합니다.
2. `Setup_GitHub_AutoRelease.bat`을 실행합니다.
3. 필수 도구가 없으면 설치를 시작하려고 `INSTALL` 입력을 요청합니다. 설치가 끝나면 PATH를 다시 읽고, 필요하면 새 PowerShell 프로세스에서 설정을 자동으로 이어갑니다.
4. GitHub CLI에서 브라우저 로그인이 필요하면 본인 계정으로 로그인합니다. 이 저장소 소유자는 `goldensw1130`입니다. 계정이 다를 때만 `SWITCH-ACCOUNT`가 필요합니다.
5. 저장소 주소 질문에는 빈칸으로 두어 기본값 `https://github.com/goldensw1130/-sw`를 사용합니다.
6. 기존 저장소 확인 질문이 나오면 `USE-EXISTING`을 입력합니다. 이 저장소는 초기 README와 릴리스 워크플로만 있으므로 설정 스크립트가 이를 확인한 뒤 소스 파일을 추가합니다.

필수 도구 설치만 진행되고 더 이상 이어지지 않으면 다음 로그를 확인하세요.

`%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log`

## 자동 릴리스와 업데이트

설정 스크립트는 소스 허용 목록, 비밀정보 패턴, Python/JavaScript 테스트, 릴리스 ZIP/manifest/SHA-256을 검사한 뒤 소스와 버전 태그를 푸시합니다. GitHub Actions는 태그와 `ShortCompassServer.py`의 `APP_VERSION`이 일치하고 테스트가 통과해야 공개 릴리스 자산을 게시합니다.

공개 저장소는 소스 코드와 릴리스 자산이 누구나 읽을 수 있습니다. 업데이트는 HTTPS, SHA-256, ZIP 경로 검사를 거치며 최종 적용은 앱에서 사용자 승인을 요구합니다.

## 보안·정책

실제 API 키, 개인 토큰, 개인키, 사용자 데이터는 Git에 커밋하지 마세요. Python/JavaScript 회귀 테스트와 비밀정보 패턴 검사는 보조 안전장치이며, 정책 준수·저작권 면책·수익 창출 승인을 보장하지 않습니다.
