'use strict';
// Extracts the real renderUpdateResult function from ShortsCompass.html and executes it with a tiny DOM mock.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync(__dirname + '/ShortsCompass.html', 'utf8');
const start = html.indexOf('function renderUpdateResult(data){');
const end = html.indexOf('\nasync function loadUpdateSettings(){', start);
assert(start >= 0 && end > start, 'renderUpdateResult exists');
const fn = html.slice(start, end);
const ids = ['updateStatus','updateReleaseNotes','updateNotice','updateManifestUrl','updateAutoCheck','updateAutoDownload','updateInterval','downloadUpdateBtn','applyUpdateBtn'];
function makeContext(){
  const elements = Object.fromEntries(ids.map(id => [id, {id, textContent:'', value:'', disabled:false, className:'', style:{display:''}}]));
  return {elements, document:{getElementById:id => elements[id] || null}};
}
function render(data){
  const c=makeContext();
  vm.runInNewContext(fn+'\nrenderUpdateResult(__testData);', {...c, __testData:data});
  return c.elements;
}
let el = render({ok:true,currentVersion:'2.38',updateAvailable:true,availableVersion:'2.39',settings:{currentVersion:'2.38',manifestUrl:'https://raw.githubusercontent.com/a/b/main/update_manifest.json',autoCheck:true,autoDownload:false,intervalHours:24,updateAvailable:true,availableVersion:'2.39',staged:false}});
assert.strictEqual(el.downloadUpdateBtn.disabled,false,'download enabled for update');
assert.strictEqual(el.applyUpdateBtn.disabled,true,'apply disabled until staged');
assert.ok(el.updateNotice.textContent.includes('2.39'),'available version shown in notice');
assert.ok(el.updateStatus.textContent.includes('2.38'),'installed version shown');
assert.strictEqual(el.updateAutoDownload.value,'false','auto-download choice rendered');

el = render({ok:true,settings:{currentVersion:'2.38',updateAvailable:false,staged:true,stagedVersion:'2.39',autoDownload:true,autoCheck:true,intervalHours:24}});
assert.strictEqual(el.downloadUpdateBtn.disabled,true,'download disabled without un-staged update');
assert.strictEqual(el.applyUpdateBtn.disabled,false,'apply enabled for staged update');
assert.ok(el.updateNotice.textContent.includes('2.39'),'staged version shown without ReferenceError');
assert.ok(el.updateNotice.textContent.includes('승인'),'manual approval requirement shown');

el = render({ok:true,configured:false,currentVersion:'2.38',updateAvailable:false,message:'피드 미설정',settings:{currentVersion:'2.38',manifestUrl:'',autoCheck:true,autoDownload:false,intervalHours:24,updateAvailable:false,staged:false}});
assert.strictEqual(el.downloadUpdateBtn.disabled,true,'download disabled when no feed');
assert.strictEqual(el.applyUpdateBtn.disabled,true,'apply disabled when no staged zip');
assert.strictEqual(el.updateNotice.style.display,'none','no stale update banner');
console.log('Test_UpdateUI.js: 13 assertions passed');
