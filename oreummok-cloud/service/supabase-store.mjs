import {readFileSync,writeFileSync,existsSync,mkdirSync,unlinkSync} from 'node:fs';
import path from 'node:path';

const names=['assistant-private.json','accounts.json','state.json','state.json.previous','remembered-devices.json','auth-events.log'];
export function supabaseStore({url,key,dir,fetcher=fetch}){
 const origin=new URL(url);
 if(origin.protocol!=='https:'||origin.pathname!=='/'||origin.search||origin.hash||origin.username||origin.password)throw Error('Invalid Supabase project URL');
 if(!key)throw Error('Supabase server secret is required');
 mkdirSync(dir,{recursive:true});
 const endpoint=origin.origin+'/rest/v1/oreummok_server_state';
 const headers={apikey:key,...(key.startsWith('sb_secret_')?{}:{Authorization:'Bearer '+key}),'Content-Type':'application/json'};
 const fail=()=>Object.assign(Error('Cloud storage unavailable; no local-only save was accepted'),{code:'CLOUD_STORAGE'});
 async function request(suffix,options={}){
  let response;try{response=await fetcher(endpoint+suffix,{...options,headers:{...headers,...options.headers},signal:AbortSignal.timeout(12000)});}catch{throw fail();}
  if(!response.ok)throw fail();
  try{return await response.json();}catch{throw fail();}
 }
 function snapshot(){const files={};for(const name of names)if(existsSync(path.join(dir,name)))files[name]=readFileSync(path.join(dir,name),'utf8');return {schema:1,files};}
 function hydrate(payload){
  if(!payload||payload.schema!==1||!payload.files||typeof payload.files!=='object'||Array.isArray(payload.files))throw fail();
  for(const [name,value]of Object.entries(payload.files))if(!names.includes(name)||typeof value!=='string')throw fail();
  for(const name of names){const file=path.join(dir,name);if(Object.hasOwn(payload.files,name))writeFileSync(file,payload.files[name],{encoding:'utf8',mode:0o600});else if(existsSync(file))unlinkSync(file);}
 }
 let chain=Promise.resolve();
 return {run(fn){
  const operation=chain.then(async()=>{
   const rows=await request('?id=eq.main&select=revision,payload');
   if(!Array.isArray(rows)||rows.length>1)throw fail();
   const old=rows[0];if(old&&(!Number.isSafeInteger(old.revision)||old.revision<1))throw fail();
   hydrate(old?old.payload:{schema:1,files:{}});
   const before=snapshot();let result;
   try{result=await fn();}catch(error){hydrate(before);throw error;}
   const after=snapshot();
   if(JSON.stringify(before)===JSON.stringify(after))return result;
   let saved;
   try{
    const row={id:'main',revision:old?old.revision+1:1,payload:after,updated_at:new Date().toISOString()};
    saved=old?await request('?id=eq.main&revision=eq.'+old.revision,{method:'PATCH',headers:{Prefer:'return=representation'},body:JSON.stringify(row)}):await request('',{method:'POST',headers:{Prefer:'return=representation'},body:JSON.stringify(row)});
   }catch(error){hydrate(before);throw error;}
   if(!Array.isArray(saved)||saved.length!==1){hydrate(before);throw Object.assign(Error('Cloud data changed. Reload and retry.'),{code:'CLOUD_CONFLICT'});}
   return result;
  });chain=operation.catch(()=>{});return operation;
 }};
}
