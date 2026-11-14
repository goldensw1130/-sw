# 오름목 무료 서버 + Supabase

배포 전 준비본입니다. 실제 서버 주소는 아직 발급되지 않았습니다.

## Render 설정
Repository: goldensw1130/-sw
Branch: oreummok-cloud-server
Root Directory: oreummok-cloud
Runtime: Node
Build Command: node --version
Start Command: node service/cloud-server.mjs
Instance Type: Free
Health Check Path: /healthz
영구 디스크 추가 또는 유료 요금제 선택은 필요하지 않습니다.

환경변수:
- NODE_VERSION: 24.11.1
- OREUMMOK_DATA_DIR: /tmp/oreummok-cache
- SUPABASE_URL: https://tccaipjgaijnnrwxuout.supabase.co
- SUPABASE_SERVICE_ROLE_KEY: Supabase 서버용 secret 또는 legacy service_role 키를 Render 비공개 환경변수에 직접 입력. 채팅/GitHub/PC앱/모바일앱에 넣지 마세요.
- OREUMMOK_ADMIN_USERNAME: 최초 클라우드 관리자 아이디
- OREUMMOK_ADMIN_PASSWORD: 최초 클라우드 관리자 비밀번호(16자 이상), 직접 입력

먼저 Supabase SQL Editor에서 supabase-schema.sql을 실행합니다. 테이블은 RLS 및 anon/authenticated 접근 차단으로 보호합니다. 클라우드 서버가 로그인과 계정별 권한을 검사합니다. Supabase Auth 로그인과 기존 오름목 로그인은 별개입니다.

오름목 자료는 서버의 임시 파일이 아니라 Supabase의 단일 버전 관리 행에 저장합니다. 각 요청 전에 자료를 다시 읽고 변경 후 조건부 저장이 확인되어야 성공 응답을 반환합니다. 충돌이나 저장 장애 때에는 성공으로 표시하지 않습니다. 파일은 5개 이름만 허용하고 경로를 외부에서 지정할 수 없습니다. 서버가 보유한 로그인 세션은 재시작 시 만료됩니다. 자동 로그인 기기 토큰은 해시로 보존됩니다. 서버 한 개를 기준으로 운영합니다.

## 기존 PC 자료 이전
기존 PC에서 JSON 백업 후 클라우드 관리자 PC의 복원 기능으로 이전합니다. 기존 계정/비밀번호는 자동 이전하지 않습니다. 클라우드 작업자 계정을 다시 생성합니다. 전환 중 양쪽 서버에서 동시에 업무 자료를 수정하지 마세요. 서버/DB 비밀키를 공개 저장소에 올리지 마세요. 업무 자료 자동 업로드는 실행하지 않았습니다.

## 한계
무료 사용량 안에서만 무료입니다. Render 무료 서버의 유휴 중지와 Supabase 무료 프로젝트의 장기간 미사용 일시정지가 있을 수 있습니다. 첫 접속 지연과 DB 사용량을 확인하세요. 외부망 실기기 검증은 배포 이후 진행합니다. 오프라인 동기화, 첨부파일 저장, 자동 외부 백업은 아직 지원하지 않습니다.

로컬 테스트 31개 통과. Supabase 실제 프로젝트 키를 사용한 저장 검증은 아직 수행하지 않았습니다.
