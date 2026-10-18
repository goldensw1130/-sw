# 숏폼 나침반

Windows용 숏폼 콘텐츠 조사·제작·성과분석 도구입니다.

## 최신 버전
- v2.49: https://github.com/goldensw1130/-sw/releases/tag/v2.49
- ZIP: https://github.com/goldensw1130/-sw/releases/download/v2.49/ShortCompass-v2.49.zip

## Windows 실행
1. 공식 Release의 `ShortCompass-v2.49.zip` 전체를 새 폴더에 압축 해제합니다.
2. `Start_ShortCompass.bat`을 실행합니다. 서버가 정상 응답한 뒤 브라우저를 엽니다.
3. 서버가 실행되는 동안 별도 `ShortCompass Local Server` 콘솔은 닫지 마세요.
4. 시작에 실패하면 로그는 `%LOCALAPPDATA%\ShortCompass\logs\start-shortcompass.log`에 기록됩니다. 시작 실패 시 오류 창을 유지하도록 되어 있습니다.

## 수정 사항
- Windows CMD에서 배치 파일이 줄 단위로 올바르게 해석되도록 ZIP 안의 모든 `.bat` 파일을 CRLF 줄바꿈으로 저장합니다.
- `start` 이후 이전 `ERRORLEVEL`이 남아 서버 시작을 실패로 잘못 판단하는 조건을 제거했습니다.
- 정상 시작 시 브라우저를 열고 임시 실행 창은 종료하며, 서버 콘솔만 유지합니다.

공개 저장소의 소스와 배포 ZIP은 누구나 볼 수 있습니다. API 키나 개인 토큰을 저장소에 커밋하지 마세요. 자동 테스트는 실사용 Windows 확인을 대체하지 않습니다.


## v2.49 콘텐츠 제작 진행 보드
- 대시보드에 소재 발굴 → 소재 검토 → 대본 제작 → 게시 성과 학습의 흐름을 추가했습니다.
- 각 단계의 수치는 저장된 항목에서만 계산하며, 게시 조회수가 입력되지 않은 게시물은 성과 기록 완료로 추정하지 않습니다.
- 각 단계 카드를 누르면 기존의 영상 찾기·소스 리스트·대본 자판기·수익화 실험실 화면으로 이동합니다.
- 넓은 화면·태블릿·모바일 레이아웃, 키보드 포커스, 진행률 접근성 표시를 보강했습니다.
