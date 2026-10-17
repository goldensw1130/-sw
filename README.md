# 숏폼 나침반

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구 및 자동 릴리스 저장소입니다.

## 현재 상태

- 저장소: https://github.com/goldensw1130/-sw
- GitHub Actions 태그 기반 릴리스 워크플로: 준비 완료
- 프로그램 소스 및 첫 Release: 아직 Windows 최초 설정을 마치지 않아 게시되지 않음
- 가장 최근 설정 창 오류 복구 패키지: 숏폼 나침반 v2.45 (이 대화에서 제공한 ZIP)

## v2.45 설정 창이 사라지는 문제

이전 설정 창은 PowerShell이 즉시 종료되거나 파일 구문 오류가 발생할 때 사용자에게 원인을 확인할 기회를 충분히 보장하지 못했습니다. v2.45의 Setup_GitHub_AutoRelease.bat은 동일 콘솔을 cmd.exe /k로 유지해 PowerShell이 종료되어도 창이 사라지지 않게 합니다. 배치 파일은 UTF-8 BOM 없이 저장되어 첫 명령 해석 문제도 줄였습니다. PowerShell의 오류는 콘솔과 로그에 표시됩니다.

로그:
%LOCALAPPDATA%\ShortCompass\logs\github-autorelease-setup.log

## 최초 설정 순서

1. v2.45 설정 복구 ZIP을 새 폴더에 압축 해제합니다. 이전 버전 폴더의 BAT만 바꿔 실행하지 마세요.
2. Setup_GitHub_AutoRelease.bat을 더블클릭합니다. 실행 창은 오류가 발생해도 남아 있어야 합니다.
3. 이미 Git/GitHub CLI/Python/Node.js 설치를 완료했다면 INSTALL을 다시 입력하지 말고, 화면에서 현재 단계를 확인합니다.
4. GitHub CLI 브라우저 로그인이 필요하면 로그인합니다. 대상 계정은 goldensw1130입니다.
5. 저장소 주소 질문에는 Enter를 눌러 기본값 https://github.com/goldensw1130/-sw를 사용합니다.
6. 기존 저장소 확인 질문이 나타나면 USE-EXISTING을 입력합니다. 저장소에는 README와 릴리스 워크플로만 준비되어 있으므로 설정 도구가 확인한 후 앱 소스를 추가할 수 있습니다.

설정 실패 시 반복해서 INSTALL을 실행하지 마세요. 화면에 보이는 실패 단계와 로그를 먼저 확인하세요.

## 자동 릴리스와 업데이트

설정 도구는 소스 허용 목록, 비밀정보 패턴, Python/JavaScript 회귀 테스트, ZIP/manifest/SHA-256 검증을 통과한 뒤 소스와 버전 태그를 푸시하도록 설계되었습니다. GitHub Actions는 태그와 ShortCompassServer.py의 APP_VERSION이 일치하고 테스트가 통과해야 공개 릴리스 자산을 게시합니다.

공개 저장소의 소스와 릴리스 자산은 누구나 읽을 수 있습니다. API 키, 개인 토큰, 개인키, 사용자 데이터를 커밋하지 마세요. 업데이트는 HTTPS·SHA-256·ZIP 경로 검사를 거치며 최종 적용은 앱에서 사용자 승인을 요구합니다.

## 보안 및 정책 한계

자동 테스트와 비밀정보 패턴 검사는 보조 수단입니다. 완전한 보안, 플랫폼 정책 통과, 저작권 면책 또는 수익 창출 승인을 보장하지 않습니다.
