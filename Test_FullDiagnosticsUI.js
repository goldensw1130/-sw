'use strict';
// Exercises the real diagnostics renderer from ShortsCompass.html without a browser or network.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync(__dirname + '/ShortsCompass.html', 'utf8');
const start = html.indexOf('function renderFullDiagnostics(data){');
const end = html.indexOf('\nasync function runFullDiagnostics()', start);
assert.ok(start >= 0 && end > start, 'renderFullDiagnostics exists');
const fn = html.slice(start, end);
const ids = ['fullDiagnosticsStatus', 'fullDiagnosticsOutput', 'downloadFullDiagnosticsBtn'];
const elements = Object.fromEntries(ids.map(id => [id, {id, textContent:'', disabled:true, className:''}]));
const context = {
  document: { getElementById: id => elements[id] || null },
  lastFullDiagnosticsData: null,
  __testData: {
    appVersion:'2.41', generatedAt:'2026-10-17T00:00:00Z',
    summary:{pass:5,warning:2,fail:0,info:1},
    checks:[{status:'PASS',title:'버전 일치',message:'일치함'}, {status:'WARN',title:'업데이트 피드',message:'아직 설정되지 않음'}],
    privacyNote:'키와 개인 경로는 포함하지 않음'
  }
};
vm.runInNewContext(fn + '\nrenderFullDiagnostics(__testData);', context);
assert.ok(elements.fullDiagnosticsStatus.textContent.includes('버전 2.41'));
assert.ok(elements.fullDiagnosticsStatus.textContent.includes('경고 2'));
assert.ok(elements.fullDiagnosticsOutput.textContent.includes('[PASS] 버전 일치'));
assert.ok(elements.fullDiagnosticsOutput.textContent.includes('[WARN] 업데이트 피드'));
assert.ok(elements.fullDiagnosticsOutput.textContent.includes('키와 개인 경로'));
assert.strictEqual(elements.downloadFullDiagnosticsBtn.disabled, false);
assert.strictEqual(context.lastFullDiagnosticsData.appVersion, '2.41');
console.log('Test_FullDiagnosticsUI.js: assertions passed');
