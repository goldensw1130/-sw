import crypto from 'node:crypto';import path from 'node:path';import {existsSync,readFileSync,writeFileSync,renameSync} from 'node:fs';
export function rememberStore(dir,clock=()=>Date.now()){
const file=path.join(dir,'remembered-devices.json'),hash=t=>crypto.createHash('sha256').update(t).digest('hex');
function read(){return existsSync(file)?JSON.parse(readFileSync(file,'utf8')):[]}
function write(rows){const tmp=file+'.tmp';writeFileSync(tmp,JSON.stringify(rows),'utf8');renameSync(tmp,file)}
return {issue(user){const token=crypto.randomBytes(32).toString('hex'),rows=read().filter(r=>r.expires>clock()).slice(-999);rows.push({hash:hash(token),id:user.id,revision:user.revision,expires:clock()+30*86400000});write(rows);return token},get(token){if(typeof token!=='string'||!/^[a-f0-9]{64}$/.test(token))return null;return read().find(r=>r.hash===hash(token)&&r.expires>clock())||null},revoke(user,token){if(typeof token!=='string')return;write(read().filter(r=>!(r.id===user.id&&r.hash===hash(token))))}};
}
