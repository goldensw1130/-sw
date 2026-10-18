# 숏폼 나침반 v2.47

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구입니다.

## Windows에서 실행

1. 공식 Release ZIP 전체를 새 폴더에 압축 해제합니다.
2. `Start_ShortCompass.bat`을 실행합니다. 앱은 로컬 `/health` 정상 응답을 확인한 뒤 브라우저를 엽니다.
3. `Start_ShortCompass_Server.bat` 서버 창은 프로그램 사용 중 열어 둡니다.
4. 시작 오류 로그: `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`

## 배포 확인

릴리스 ZIP 빌더가 모든 Windows `.bat` 파일의 줄 끝을 CRLF로 고정하고, 회귀 테스트가 이를 검증합니다. Windows 배치 파일은 BOM 없이 배포합니다.
