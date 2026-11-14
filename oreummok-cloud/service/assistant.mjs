import {answerRequest} from './assistant-prompt.mjs';
import {requirePermission} from './permissions.mjs';
import {totals} from './core.mjs';
import {createHash} from 'node:crypto';
import {stairGeometry} from './stairs.mjs';
const numeric=['quantity','watts','length','wattsPerM','voltage','supply','tax','materialCost','laborCost','otherCost'];
export function reviewContext(state,user,args={}){
  const kind=args.kind||'general';if(kind==='chat')return {context:{kind:'chat'},notes:[],previewToken:'',notice:'자유 질문 상담'};let context={},notes=[];if(kind==='general'){const topic=['stairs','quote','lighting'].includes(args.topic)?args.topic:'stairs';context={kind:'general',topic};notes.push(topic==='quote'?'견적 준비: 수량·단가·자재 손실률·인건비·철거·운반·폐기·출장비·세금·하자 비용과 지급 조건을 정리하세요.':topic==='lighting'?'조명 준비: 등기구 수량·소비전력·LED 길이·전원장치·배선 경로·제어 방식·습기 노출 조건을 확인하세요.':'계단 준비: 바닥 마감 두께·골조 상태·철거 범위·난간·벽체 고정·운반 동선·전기 우회 배선을 실측하세요.');}
  if(kind==='quotes'){
    requirePermission(user,'quotes.read');const q=(state.quotes||[]).find(x=>x.id===args.id);if(!q)throw Error('검토할 견적을 다시 선택하세요.');
    context={kind,items:q.items.map(i=>({qty:+i.qty,cost:+i.cost,...(i.sale===undefined?{}:{sale:+i.sale})})),margin:+q.margin,taxMode:q.taxMode,vat:q.vat,vatRate:q.vatRate,discount:q.discount};
    context.calculation=totals(context);
    if(!q.items.length)notes.push('견적 품목이 없습니다.');
    if(q.items.some(i=>+i.qty===0))notes.push('수량이 0인 품목을 확인하세요.');
    if(q.items.some(i=>+i.cost===0))notes.push('원가가 0인 품목의 자재·인건비 누락 여부를 확인하세요.');
    if(context.calculation.profit<=0)notes.push('예상 이익이 0원 이하입니다. 원가·할인·판매가를 재검토하세요.');
    notes.push('철거·폐기물·운반·양중·보양·마감·전기 우회·출장비 포함 여부를 확인하세요.','실측 후 변경 공사와 추가 비용의 승인 조건을 견적서에 명시하세요.');
  }else if(kind==='lighting'){
    requirePermission(user,'lighting.read');const r=(state.lighting||[]).find(x=>x.id===args.id);if(!r)throw Error('검토할 조명 공사를 다시 선택하세요.');
    context={kind,...Object.fromEntries(numeric.map(k=>[k,Number(r[k]||0)]))};
    context.loadW=context.quantity*context.watts+context.length*context.wattsPerM;
    if(context.loadW===0)notes.push('조명 수량·소비전력·LED 길이를 입력하세요.');
    if(context.supply<=context.materialCost+context.laborCost+context.otherCost)notes.push('공급가가 예상 원가 이하입니다.');
    notes.push('전원장치 용량·전압강하·배선 규격·차단기·접지·방수등급은 현장 조건에 맞춰 검토하세요.','전원 차단·무전압 확인·절연·접지·점등 시험 결과를 직접 기록하세요.');
  }else if(kind==='designs'){
    requirePermission(user,'designs.read');const d=(state.designs||[]).find(x=>x.id===args.id);if(!d)throw Error('검토할 3D 설계를 다시 선택하세요.');
    const model=stairGeometry(d.inputs||{});context={kind,inputs:model.inputs,rise:model.rise,pitch:model.pitch,treadCount:model.treadCount,footprintX:model.footprintX,footprintY:model.footprintY};
    notes.push(...model.issues.map(x=>x.text));
    if(model.geometryChecksPassed)notes.push('입력 치수 검사 통과: 실제 시공 전 실측과 구조 검토가 필요합니다.');
  }else if(kind!=='general')throw Error('지원하지 않는 검토 항목입니다.');
  notes.push('계단 실측: 마감 층고·단높이·디딤판·유효 폭·머리 공간·개구부를 확인하세요.','3D 치수 검사는 구조 안전 승인이나 법규 적합 판정을 대신하지 않습니다.');
  return {context,notes,previewToken:createHash('sha256').update(JSON.stringify(context)).digest('hex'),notice:'무료 규칙 기반 자동검토입니다. AI 답변과 구분됩니다. 원가·치수는 등록 자료 기준이며 현장 확인이 필요합니다.'};
}
export function aiStatus(env=process.env){return {configured:!!env.OREUMMOK_GEMINI_API_KEY&&env.OREUMMOK_AI_FREE_PROJECT==='true',provider:'Gemini',model:env.OREUMMOK_AI_MODEL||'gemini-2.5-flash-lite',notice:'관리자 API 키 설정에서 결제 연결이 없는 무료 프로젝트 키를 입력하세요. 무료 한도 초과 시 자동 유료 전환하지 않습니다. 무료 API 입력은 제공업체의 서비스 개선에 사용될 수 있습니다.'};}
export function createAssistant({env=process.env,fetcher=fetch,now=Date.now}={}){
 const limits=new Map();
 return async function ask(user,args,review){
  if(!aiStatus(env).configured)throw Error('생성형 AI가 아직 연결되지 않았습니다. 무료 자동검토를 먼저 이용하세요.');
  if(args.consent!==true)throw Error('외부 AI 전송 내용을 확인하고 동의하세요.');
  if(args.kind!=='chat'&&args.previewToken!==review.previewToken)throw Error('검토 자료가 변경되었거나 전송 자료를 확인하지 않았습니다. 자동검토를 다시 실행하세요.');
  const question=typeof args.question==='string'?args.question.trim():'';
  if(!question||question.length>6000)throw Error('질문을 1~6,000자로 입력하세요.');
  const payload=answerRequest({...args,question},review);
  const key=user.username,t=now(),old=limits.get(key)||{at:0,count:0,day:''},day=new Date(t).toISOString().slice(0,10);
  if(old.at&&t-old.at<15000)throw Error('AI 요청은 15초 간격으로 이용하세요.');
  const count=old.day===day?old.count:0;if(count>=30)throw Error('오름목의 계정별 일일 AI 요청 한도 30회에 도달했습니다.');
  limits.set(key,{at:t,count:count+1,day});if(limits.size>1000)for(const[k,v]of limits)if(v.day!==day)limits.delete(k);
  const model=env.OREUMMOK_AI_MODEL||'gemini-2.5-flash-lite';if(!/^gemini-[a-z0-9.-]+$/.test(model))throw Error('AI 모델 설정 오류입니다.');
  let response;try{response=await fetcher('https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent',{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':env.OREUMMOK_GEMINI_API_KEY},signal:AbortSignal.timeout(45000),body:JSON.stringify(payload)});}catch{throw Error('AI 연결 시간이 초과되었거나 연결에 실패했습니다. 자동검토 결과는 계속 이용할 수 있습니다.');}
  if(!response.ok)throw Error(response.status===429?'무료 AI 요청 한도에 도달했습니다. 잠시 후 다시 이용하세요. 유료 모델로 전환하지 않았습니다.':'AI 제공업체 연결 오류입니다. 서버의 키·모델 설정을 확인하세요.');
  const data=await response.json(),candidate=data.candidates?.[0],answer=(candidate?.content?.parts||[]).filter(p=>!p.thought).map(p=>p.text||'').join('\n').trim();
  if(!answer)throw Error('AI 답변이 비어 있거나 제공업체에서 제한했습니다. 질문을 바꿔 다시 시도하세요.');
  return {answer:answer.slice(0,28000),truncated:candidate?.finishReason==='MAX_TOKENS'||answer.length>28000,provider:'Gemini',model,notice:'AI 제안이며 오류가 있을 수 있습니다. 현장 실측·공사비·구조·전기 검토는 담당자가 확인하세요.'};
 };
}
