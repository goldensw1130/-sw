# 숏폼 나침반

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구 및 자동 릴리스 저장소입니다.

## 최초 설정

이 저장소에는 현재 GitHub Actions 릴리스 워크플로가 준비되어 있습니다. 앱 소스는 Windows에서 **숏폼 나침반 v2.43** ZIP을 새 폴더에 풀고 `Setup_GitHub_AutoRelease.bat`을 실행하여 추가할 수 있습니다.

- 기본 저장소: https://github.com/goldensw1130/-sw
- 로그인 계정이 `goldensw1130`인지 확인합니다. 다른 계정이면 설정 단계에서 `SWITCH-ACCOUNT`를 선택합니다.
- 기존 저장소 확인 시 `USE-EXISTING`을 입력합니다.
- 스크립트는 테스트와 릴리스 사전 검증 후에만 소스와 `v2.43` 태그를 푸시합니다.
- GitHub Actions는 태그와 소스 버전이 일치하고 모든 테스트가 통과할 때 ZIP, `update_manifest.json`, `SHA256SUMS.txt`를 릴리스 자산으로 게시합니다.

## 자동 업데이트

릴리스는 공개된 `update_manifest.json`을 사용합니다. 공개 저장소는 소스 코드와 릴리스 자산이 누구나 읽을 수 있다는 점에 유의하세요. 업데이트는 HTTPS, SHA-256, ZIP 경로 검사를 거치며 최종 적용은 앱에서 사용자의 승인을 요구합니다.

## 보안·정책

실제 API 키, 개인 토큰, 개인키, 사용자 데이터는 Git에 커밋하지 마세요. Python/JavaScript 회귀 테스트와 비밀정보 패턴 검사는 보조 안전장치이며, 정책 준수·저작권 면책·수익 창출 승인을 보장하지 않습니다.
