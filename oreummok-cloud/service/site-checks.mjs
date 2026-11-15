export const siteTemplate=[
 ['applicability','적용 기준 — 건물·계단 용도와 현행 법령·허가도서·검토자 기록 (일반 기본치로 법규 자동 판정 금지)'],
 ['batch','목재 로트 — 입고/시공 전 함수율·측정점·측정기·실내 온습도·제조사 기준 기록'],
 ['cutting','재단 — 부재번호·결방향·톱날 손실·가공여유·재확인 담당자·도면 개정번호'],
 ['variation','추가공사 — 철거 후 예상외 배선/바탕 상태·증감액·일정 영향·고객 확인 증빙'],
 ['cure','양생 — 접착제·도장 제조사 조건과 보행 가능 시각·신축 여유 확인'],
 ['service','유지보수 — LED 전원장치·접속부 점검구와 교체 동선·제품번호 기록'],

 ['survey','실측 · 바닥 마감 포함 층고와 가용 공간 기록'],['level','실측 · 첫단·끝단·누적 레벨 및 단높이 편차 확인'],['opening','실측 · 개구부·보·문·상부 유효높이 간섭 확인'],['structure','구조 · 골조 상태와 하중·고정 상세의 담당자 검토'],['utilities','철거 전 · 매립 배선·배관 위치 및 우회 범위 확인'],['isolation','전기 · 작업 전 전원 차단·검전·재투입 방지 확인'],['wood','자재 · 수종·규격·함수 상태·현장 적응 및 결함 확인'],['finish','목공 · 발판 고정·단차·흔들림·모서리·미끄럼 확인'],['guard','난간 · 손스침·틈새·고정 상태와 적용 기준 검토'],['led','LED · 전원장치 정격·부하·방열·점검 접근성 확인'],['cable','전기 · 케이블 보호·접속부·접지 및 보호장치 검토'],['light','점등 · 센서·스위치·눈부심·밝기 시험 결과 기록'],['handover','인계 · 보수 항목·고객 확인·관리 안내·사진 위치 기록']
].map(([key,label])=>({key,label,done:false,note:''}));
export function validateChecks(state){if(state.siteChecks===undefined)return;if(!Array.isArray(state.siteChecks)||state.siteChecks.length>5000)throw Error('점검 목록 형식 오류');const ids=new Set();for(const r of state.siteChecks){if(!r||!/^[a-f0-9-]{36}$/i.test(r.id)||ids.has(r.id)||typeof r.name!=='string'||!r.name.trim()||r.name.length>250||!state.projects.some(p=>p.id===r.project)||!Array.isArray(r.items)||r.items.length>100)throw Error('점검명·연결 현장·항목을 확인하세요.');ids.add(r.id);const keys=new Set();for(const i of r.items){if(!i||typeof i.key!=='string'||keys.has(i.key)||typeof i.label!=='string'||i.label.length>500||typeof i.done!=='boolean'||typeof i.note!=='string'||i.note.length>2000)throw Error('점검 항목 형식 오류');keys.add(i.key);}if(r.note!==undefined&&(typeof r.note!=='string'||r.note.length>10000))throw Error('점검 메모가 너무 깁니다.');}}
