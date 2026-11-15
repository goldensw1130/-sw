
const f=(key,label,type='text',options='')=>({key,label,type,options});
export const stairWorkModules=[
{key:'stairFiles',label:'계단 제작 · 현장 기술기록',fields:[
f('name','기술기록명'),f('project','현장','projects'),f('date','실측일','date'),
f('status','공정 기록 단계','select','실측중,제작준비,준공인계'),
f('use','건물 용도 / 계단 용도 / 적용대상 검토'),f('ruleReview','적용 법령·설계도서·검토자 및 확인일','note'),
f('measurement','마감 전후 층고·각 단 높이·폭·대각·벽체 오차 실측 mm','note'),
f('opening','보·천장·문 열림·유효높이·운반 동선 실측','note'),
f('structureReview','지지구조·앵커·하중 검토 근거 / 검토자','note'),
f('utilityReview','철거 전 매립 배선·배관 탐지 및 우회 / 정전 계획','note'),
f('woodBatch','수종·등급·로트·공급처·입고일'),f('moisture','입고 / 시공 전 함수율 측정점·측정기·온습도·제조사 기준','note'),
f('cutList','부재 번호·수량·결방향·가공치수·재단여유·톱날손실·불량 여유','note'),
f('fixing','기재·고정구·접착제 제품 / 양생·신축 여유 제조사 근거','note'),
f('ledPlan','LED 전압·W/m·길이·회로별 부하·전원장치 허용부하·전압강하 검토','note'),
f('serviceAccess','전원장치 점검구·방열·배선 보호·접속부·교체 동선','note'),
f('reviewer','제작 전 현장 확인 담당자'),f('reviewDate','제작 전 확인일','date'),
f('testRecord','준공 실측·흔들림·미끄럼·난간·접지/보호·점등 및 시험 기록','note'),
f('handover','고객 인수기록·미완료 항목·관리법·보증 범위·AS 연락처','note'),
f('evidence','사진 / 도면 / 시험성적서 파일 위치','note'),
f('note','출처: 건축물방화구조규칙 제15조 / USDA Wood Handbook 4장. 법규 적합·구조 안전 자동 인증 아님','note')]},
{key:'changeOrders',label:'추가공사 · 변경 합의 기록',fields:[
f('name','변경명'),f('project','현장','projects'),f('date','요청일','date'),f('requester','요청자'),
f('before','기존 계약 범위','note'),f('after','변경 범위·수량·자재·도면 개정번호','note'),
f('amount','변경 공급가 (증액은 양수, 감액은 별도 기록)','number'),f('tax','변경 부가세','number'),f('cost','추가 예상원가','number'),
f('scheduleImpact','일정 영향 / 작업 보류 범위'),f('status','합의 기록 상태','select','검토중,고객확인,시공완료,취소'),
f('confirmation','고객 확인 증빙 위치 / 확인자·확인일 (앱 전자서명 아님)','note'),
f('note','기존 견적·계약·입금은 자동 변경하지 않습니다. 필요 시 별도 개정·정산','note')]}
];
export function validateStairWork(key,r){
 if(!r.project)throw Error('현장을 먼저 연결하세요.');
 const stages=key==='stairFiles'?['실측중','제작준비','준공인계']:['검토중','고객확인','시공완료','취소'];
 if(!stages.includes(r.status))throw Error('공정 기록 상태를 확인하세요.');
 const needs=key==='stairFiles'&&r.status!=='실측중'?['use','ruleReview','measurement','opening','structureReview','utilityReview','woodBatch','moisture','cutList','fixing','reviewer','reviewDate']:key==='changeOrders'&&['고객확인','시공완료'].includes(r.status)?['before','after','confirmation']:[];
 if(key==='stairFiles'&&r.status==='준공인계')needs.push('testRecord','handover','evidence');
 for(const field of needs)if(typeof r[field]!=='string'||!r[field].trim())throw Error('단계 변경 전에 필수 근거를 입력하세요: '+field);
 for(const field of ['amount','tax','cost'])if(r[field]!==undefined&&(!Number.isFinite(+r[field])||+r[field]<0||+r[field]>1e12))throw Error('금액을 확인하세요.');
 if(r.ledPlan?.trim()&&['제작준비','준공인계'].includes(r.status)&&!r.serviceAccess?.trim())throw Error('LED 적용 시 전원장치 점검·교체 접근 계획을 기록하세요.');
}
