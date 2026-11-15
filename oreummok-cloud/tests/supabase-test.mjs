import {test} from 'node:test';import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,rmSync,existsSync} from 'node:fs';import path from 'node:path';
import {supabaseStore} from '../service/supabase-store.mjs';
function fake(){let row=null,offline=false,conflict=false;return {setOffline:v=>offline=v,setConflict:v=>conflict=v,fetcher:async(url,opts)=>{
 if(offline)throw Error('network down');const method=opts.method||'GET';let result;
 if(method==='GET')result=row?[structuredClone(row)]:[];
 else if(method==='POST'){assert.equal(row,null);row=JSON.parse(opts.body);result=[row];}
 else if(method==='PATCH'){if(conflict)result=[];else{assert.equal(new URL(url).searchParams.get('revision'),'eq.'+row.revision);row=JSON.parse(opts.body);result=[row];}}
 return {ok:true,json:async()=>structuredClone(result)};
 }};}
test('Supabase persists across empty cache restart and restores account, business data, remembered devices',async()=>{
 const dir=mkdtempSync(path.join(process.cwd(),'.qa-supabase-'));const db=fake();const config={url:'https://example.supabase.co',key:'qa-only-not-real',fetcher:db.fetcher};
 try{
  const a=supabaseStore({...config,dir:path.join(dir,'a')});
  await a.run(()=>{for(const name of ['accounts.json','state.json','remembered-devices.json','assistant-private.json'])writeFileSync(path.join(dir,'a',name),JSON.stringify({sample:name}));});
  const b=supabaseStore({...config,dir:path.join(dir,'b')});
  await b.run(()=>{assert.equal(JSON.parse(readFileSync(path.join(dir,'b','state.json'))).sample,'state.json');assert.equal(JSON.parse(readFileSync(path.join(dir,'b','assistant-private.json'))).sample,'assistant-private.json');});
  db.setOffline(true);let called=false;await assert.rejects(b.run(()=>{called=true;}),/storage unavailable/);assert.equal(called,false);db.setOffline(false);
  db.setConflict(true);await assert.rejects(b.run(()=>writeFileSync(path.join(dir,'b','state.json'),'changed')),/changed/);
  assert.notEqual(readFileSync(path.join(dir,'b','state.json'),'utf8'),'changed');
 }finally{rmSync(dir,{recursive:true,force:true});}
});
test('Failed first operation restores empty cache and does not accept unpersisted data',async()=>{
 const dir=mkdtempSync(path.join(process.cwd(),'.qa-supabase-'));const db=fake();try{
  const store=supabaseStore({url:'https://example.supabase.co',key:'qa-only',dir,fetcher:db.fetcher});
  await assert.rejects(store.run(()=>{writeFileSync(path.join(dir,'accounts.json'),'temporary');throw Error('operation rejected');}));
  assert.equal(existsSync(path.join(dir,'accounts.json')),false);
 }finally{rmSync(dir,{recursive:true,force:true});}
});

test('receipt-return history and stock survive a new cloud cache',async()=>{const {createEngine,empty}=await import('../service/engine.mjs');const dir=mkdtempSync(path.join(process.cwd(),'.qa-supabase-return-')),db=fake(),config={url:'https://example.supabase.co',key:'qa-only',fetcher:db.fetcher},order=crypto.randomUUID(),material=crypto.randomUUID();try{const aDir=path.join(dir,'a'),bDir=path.join(dir,'b'),a=supabaseStore({...config,dir:aDir});await a.run(async()=>{const e=createEngine(aDir);await e.call('setup',{username:'owner',password:'QA-Cloud-Return-Password-123'});const session=(await e.call('login',{username:'owner',password:'QA-Cloud-Return-Password-123'})).session;const state=empty();state.materials.push({id:material,name:'QA 원목',stock:2,cost:10});state.orders.push({id:order,name:'QA 발주',qty:5,cost:10,material,status:'발주'});await e.call('save',{state,version:null},session);let r=await e.call('load',{},session);r.state.orders[0].received=true;r.state.orders[0].status='입고완료';r.state.materials[0].stock=7;await e.call('save',{state:r.state,version:r.version},session);r=await e.call('load',{},session);await e.call('returnReceipt',{id:order,qty:1,kind:'공급처반품',reason:'QA 반품',requestId:crypto.randomUUID(),version:r.version},session);});const b=supabaseStore({...config,dir:bDir});await b.run(async()=>{const e=createEngine(bDir),session=(await e.call('login',{username:'owner',password:'QA-Cloud-Return-Password-123'})).session,r=await e.call('load',{},session);assert.equal(r.state.materials[0].stock,6);assert.equal(r.state.orders[0].returnedQty,1);assert.equal(r.state.orders[0].receiptReturns[0].reason,'QA 반품');assert.equal(r.state.orders[0].receiptReturns[0].by,'owner');});}finally{if(!dir.startsWith(path.join(process.cwd(),'.qa-supabase-return-')))throw Error('Bad cleanup target');rmSync(dir,{recursive:true,force:true});}});
