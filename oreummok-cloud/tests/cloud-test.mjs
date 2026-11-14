import {test} from 'node:test';import assert from 'node:assert/strict';import {mkdtempSync,rmSync} from 'node:fs';import path from 'node:path';import {cloudServer} from '../service/cloud-server.mjs';
test('cloud login persists across restart; HTTPS, setup and unauthenticated data denied',async()=>{
 const dir=mkdtempSync(path.join(process.cwd(),'.qa-cloud-'));let server;
 try{
  server=await cloudServer({dir,username:'cloudowner',password:'Cloud-QA-Password-123',host:'127.0.0.1',port:0});
  const call=async(method,args={},session='',https=true)=>{const r=await fetch('http://127.0.0.1:'+server.address().port+'/rpc',{method:'POST',headers:{'Content-Type':'application/json',...(https?{'X-Forwarded-Proto':'https'}:{})},body:JSON.stringify({method,args,session})});return {status:r.status,body:await r.json()};};
  assert.equal((await call('status',{},'',false)).status,426);
  assert.equal((await call('setup')).status,403);
  assert.equal((await call('load')).body.ok,false);
  assert.equal((await call('login',{username:'cloudowner',password:'wrong'})).body.ok,false);
  let login=await call('login',{username:'cloudowner',password:'Cloud-QA-Password-123'});assert.equal(login.body.result.user.role,'admin');
  assert.equal((await call('load',{},login.body.result.session)).body.ok,true);
  await new Promise(r=>server.close(r));
  server=await cloudServer({dir,host:'127.0.0.1',port:0});
  assert.equal((await call('load',{},login.body.result.session)).body.ok,false);
  login=await call('login',{username:'cloudowner',password:'Cloud-QA-Password-123'});assert.equal(login.body.ok,true);
 }finally{if(server)await new Promise(r=>server.close(r));rmSync(dir,{recursive:true,force:true});}
});
