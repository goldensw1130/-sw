
import {requirePermission} from './permissions.mjs';
const uuid=v=>typeof v==='string'&&/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(v);
const kinds=['입고정정','공급처반품'];
export function validateReceiptReturns(order){if(order.returnedQty!==undefined&&(!Number.isFinite(+order.returnedQty)||+order.returnedQty<0))throw Error("반품 누적 수량 형식을 확인하세요.");
 const rows=order.receiptReturns;if(rows===undefined){if(+order.returnedQty>0)throw Error('반품 수량에는 원본 이력이 필요합니다.');return;}
 if(!Array.isArray(rows)||rows.length>500)throw Error('반품 이력 형식을 확인하세요.');
 const ids=new Set(),requests=new Set();let total=0;
 for(const r of rows){if(!r||!uuid(r.id)||!uuid(r.requestId)||ids.has(r.id)||requests.has(r.requestId)||!Number.isFinite(+r.qty)||+r.qty<=0||+r.qty>1e12||!kinds.includes(r.kind)||typeof r.reason!=='string'||!r.reason.trim()||r.reason.length>1000||typeof r.by!=='string'||!r.by||r.by.length>100||!Number.isFinite(Date.parse(r.at)))throw Error('반품 이력의 수량·번호·사유·처리자를 확인하세요.');ids.add(r.id);requests.add(r.requestId);total+=+r.qty;}
 if(order.received!==true||!Number.isFinite(+order.returnedQty)||+order.returnedQty<0||Math.abs(+order.returnedQty-total)>1e-6||total>+order.qty+1e-6)throw Error('반품 이력 합계와 원입고 수량이 일치하지 않습니다.');
}
export function returnReceipt(state,args,user){
 requirePermission(user,'orders.write');requirePermission(user,'materials.write');
 const qty=Number(args.qty),reason=String(args.reason||'').trim(),kind=args.kind;
 if(!uuid(args.requestId)||!Number.isFinite(qty)||qty<=0||qty>1e12||Math.abs(qty*1000-Math.round(qty*1000))>1e-5||!reason||reason.length>1000||!kinds.includes(kind))throw Error('수량(소수점 3자리까지)·처리 종류·사유를 확인하세요.');
 for(const order of state.orders||[]){const prior=(order.receiptReturns||[]).find(r=>r.requestId===args.requestId);if(prior){if(order.id!==args.id||+prior.qty!==qty||prior.kind!==kind||prior.reason!==reason||prior.by!==user.username)throw Error('같은 요청 번호가 다른 반품 내용에 사용됐습니다.');return {record:order,entry:prior,idempotent:true};}}
 const order=(state.orders||[]).find(o=>o.id===args.id);
 if(!order||order.received!==true)throw Error('입고 반영된 발주를 선택하세요.');
 validateReceiptReturns(order);
 if((order.receiptReturns||[]).length>=500)throw Error('이 발주의 반품 이력 한도에 도달했습니다.');
 const returned=(order.receiptReturns||[]).reduce((sum,r)=>sum+Number(r.qty),0),remaining=Number(order.qty)-returned;
 if(qty>remaining+1e-9)throw Error('원입고 잔여 수량보다 많이 반품할 수 없습니다.');
 const material=(state.materials||[]).find(m=>m.id===order.material),stock=Number(material?.stock);
 if(!material||!Number.isFinite(stock)||stock<qty-1e-9)throw Error('현재 재고가 부족합니다. 이미 출고된 수량을 먼저 확인하세요.');
 const after=Math.max(0,Number((stock-qty).toFixed(6))),entry={id:crypto.randomUUID(),requestId:args.requestId,qty,kind,reason,by:user.username,at:new Date().toISOString()};
 material.stock=after;order.receiptReturns||=[];order.receiptReturns.push(entry);order.returnedQty=Number((returned+qty).toFixed(6));return {record:order,entry,notice:'재고만 차감했습니다. 공급처 환불·지급금 정산은 별도 장부에 기록하세요.'};
}
