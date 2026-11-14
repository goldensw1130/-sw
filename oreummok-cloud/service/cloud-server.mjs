import http from 'node:http';
import path from 'node:path';
import {createEngine} from './engine.mjs';
import {pathToFileURL} from 'node:url';

// One instance only: the engine uses atomic local files on an attached persistent disk.
export async function cloudServer({dir,username,password,host='0.0.0.0',port=10000,requireHttps=true}={}) {
 if(!dir||!path.isAbsolute(dir))throw Error('An absolute persistent data directory is required');
 const engine=createEngine(dir);
 if(!(await engine.call('status')).initialized){
  if(!username||typeof password!=='string'||password.length<16)throw Error('Initial administrator credentials (password >=16 characters) are required');
  await engine.call('setup',{username,password,name:'������ ������'});
 }
 let queue=Promise.resolve(),pending=0;
 const rates=new Map();
 const server=http.createServer(async(req,res)=>{
  res.setHeader('Content-Type','application/json; charset=utf-8');
  res.setHeader('Cache-Control','no-store');
  res.setHeader('X-Content-Type-Options','nosniff');
  const send=(status,body)=>{res.writeHead(status);res.end(JSON.stringify(body));};
  if(req.method==='GET'&&req.url==='/healthz')return send(200,{ok:true,service:'oreummok-cloud'});
  // Enable only behind the hosting provider's trusted HTTPS proxy. Never expose this port directly.
  if(requireHttps&&req.headers['x-forwarded-proto']!=='https')return send(426,{ok:false,error:'HTTPS ������ �ʿ��մϴ�.'});
  if(req.method!=='POST'||req.url!=='/rpc')return send(404,{ok:false,error:'Not found'});
  if(req.headers.origin||!(req.headers['content-type']||'').startsWith('application/json'))return send(415,{ok:false,error:'Native JSON API only'});
  if(pending>=32)return send(503,{ok:false,error:'���� ó�� ���Դϴ�. ��� �� �ٽ� �õ��ϼ���.'});
  const peer=req.socket.remoteAddress||'unknown';
  // Do not trust caller-controlled X-Forwarded-For. A global proxy bucket is deliberately conservative.
  const now=Date.now(),rate=rates.get(peer);
  if(!rate||rate.until<now)rates.set(peer,{until:now+60000,count:1});
  else if(++rate.count>180)return send(429,{ok:false,error:'��û�� �����ϴ�. ��� �� �ٽ� �õ��ϼ���.'});
  for(const[k,v]of rates)if(v.until<now)rates.delete(k);
  pending++;
  try {
   let size=0;const chunks=[];
   for await(const c of req){size+=c.length;if(size>1600000){send(413,{ok:false,error:'��û ũ�� �ʰ�'});return;}chunks.push(c);}
   let q;try{q=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{return send(400,{ok:false,error:'�߸��� JSON ��û'});}
   if(!q||typeof q!=='object'||typeof q.method!=='string'||q.args&&(typeof q.args!=='object'||Array.isArray(q.args)))return send(400,{ok:false,error:'�߸��� ��û'});
   if(q.method==='setup'||q.method==='network')return send(403,{ok:false,error:'Ŭ���忡�� ����� �� ���� �۾��Դϴ�.'});
   const operation=queue.then(()=>engine.call(q.method,q.args||{},q.session||'','cloud-client'));
   queue=operation.catch(()=>{});
   const result=await operation;return send(200,{ok:true,result});
  }catch(e){
   // Filesystem errors may contain private paths. Keep credentials and request bodies out of logs.
   const safe=e.code?'���� �ڷ� ó�� �����Դϴ�. �����ڿ��� �����ϼ���.':String(e.message).slice(0,240);
   return send(400,{ok:false,error:safe});
  }finally{pending--;}
 });
 server.requestTimeout=20000;server.headersTimeout=15000;
 await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,host,resolve);});
 return server;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 const server=await cloudServer({dir:process.env.OREUMMOK_DATA_DIR,username:process.env.OREUMMOK_ADMIN_USERNAME,password:process.env.OREUMMOK_ADMIN_PASSWORD,port:Number(process.env.PORT||10000)});
 console.log('OreumMok cloud API ready');
 for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>process.exit(0)));
}
