# 숏폼 나침반

자동 릴리스 저장소입니다. 앱 소스 버전은 2.45이며 GitHub Actions가 태그 v2.45를 받아 테스트 후 릴리스 ZIP, 업데이트 manifest, SHA-256 파일을 게시합니다.

## 새 버전 배포

1. 소스 코드를 수정하고 ShortCompassServer.py의 APP_VERSION, HTML 제목/하단/백업 버전과 릴리스 노트를 동일하게 맞춥니다.
2. Python 및 JavaScript 회귀 테스트를 실행합니다.
3. 커밋 후 해당 커밋에서 새 버전 태그를 만들고 푸시합니다. 예: git tag v2.45 및 git push origin v2.45.
4. Actions 실행이 통과하면 GitHub Releases에 ZIP, update_manifest.json, SHA256SUMS.txt가 게시됩니다.

업데이트 manifest: https://github.com/goldensw1130/-sw/releases/latest/download/update_manifest.json

이 저장소가 Private이면 인증 없는 앱 업데이트 클라이언트는 릴리스 자산에 접근할 수 없습니다.
