# 숏폼 나침반

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구 및 자동 릴리스 저장소입니다.

## 현재 상태

- 저장소: https://github.com/goldensw1130/-sw
- 최신 버전: v2.46
- 릴리스: https://github.com/goldensw1130/-sw/releases/tag/v2.46
- GitHub Actions: Python/JavaScript 회귀 테스트, ZIP/manifest/SHA-256 생성 및 공개 릴리스 검증 완료

## Windows 실행 및 시작 오류 진단

1. 최신 Release의 `ShortCompass-v2.46.zip`을 새 폴더에 압축 해제합니다.
2. `Start_ShortCompass.bat`을 실행합니다. 브라우저를 열기 전에 로컬 서버의 `/health` 상태와 버전을 확인합니다.
3. `Start_ShortCompass_Server.bat`은 서버를 별도 콘솔에서 실행합니다. 검색·AI 프록시·업데이트 기능을 사용하는 동안 서버 창을 닫지 마세요.
4. 실행이 실패하면 창이 즉시 닫히지 않고 로그 경로를 표시합니다. 로그는 `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`에 저장됩니다.

## 자동 릴리스와 업데이트

- 버전 태그 `v*`를 푸시하면 GitHub Actions가 테스트 후 해당 버전의 공개 Release 자산을 생성합니다.
- `main`에 `release: publish ShortCompass v2.46` 형식의 커밋을 푸시해도 소스의 `APP_VERSION`이 일치하는지 확인하고 같은 버전의 Release를 게시합니다. 일반 커밋은 배포하지 않습니다.
- ZIP은 앱 파일 허용 목록, SHA-256 및 ZIP 무결성 검사를 포함합니다. 업데이트 적용 전에는 앱에서 최종 승인을 요구합니다.

공개 저장소의 소스와 릴리스 자산은 누구나 읽을 수 있습니다. API 키, 개인 토큰, 개인키, 사용자 데이터를 커밋하지 마세요. 자동 테스트와 비밀정보 패턴 검사는 보조 수단이며 완전한 보안을 보장하지 않습니다.
