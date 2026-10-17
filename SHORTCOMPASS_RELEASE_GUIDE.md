# 숏폼 나침반 v2.46

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구입니다. GitHub Actions는 `v*` 태그 푸시와 `release: publish ShortCompass v*` 형식의 `main` 릴리스 커밋에서 테스트를 실행하고 릴리스 ZIP, 업데이트 manifest, SHA-256 파일을 게시합니다.

## Windows에서 실행

1. ZIP 전체를 새 폴더에 압축 해제합니다.
2. `Start_ShortCompass.bat`을 실행합니다. 서버 `/health` 응답을 확인한 후 브라우저가 열립니다.
3. `Start_ShortCompass_Server.bat` 서버 창은 앱에서 로컬 검색·AI·업데이트 기능을 쓸 때 열어 둡니다.
4. 시작 실패 로그: `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`

## 새 버전 배포

1. 앱 버전, HTML 제목/하단/백업 메타데이터, 테스트와 릴리스 노트를 함께 갱신합니다.
2. 회귀 테스트와 `Prepare_Release.py` 사전 검증을 통과시킵니다.
3. `release: publish ShortCompass v2.47`처럼 새 버전의 릴리스 커밋을 `main`에 올리거나, 동일 커밋에 버전 일치 태그 `v2.47`을 푸시합니다.
4. GitHub Actions의 성공과 Release 자산을 확인합니다.
