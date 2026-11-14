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
