/* Optional runtime regression checks for A/B analytics. Requires Node.js; does not access network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, 'ShortsCompass.html'), 'utf8');
const start = source.indexOf('function validABDate(value)');
const end = source.indexOf('function fmtABValue(info,value)', start);
if (start < 0 || end < 0) throw new Error('Could not locate A/B helper functions in ShortsCompass.html');
const helpers = source.slice(start, end);
const sandbox = { Date, Number, Math, Array, Object, String };
const api = vm.runInNewContext(`${helpers}\n({validABDate,abWilsonInterval,abMetricUncertainty,assessABTest})`, sandbox);

const mid = api.abWilsonInterval(50, 100);
assert(mid && mid.low > 0.40 && mid.low < 0.41 && mid.high > 0.59 && mid.high < 0.60, 'Wilson interval for 50/100 should be plausible');
let test = {
  metric: 'ctr', variable: 'hook',
  a: { views: 1000, clicks: 20, conversions: 2, revenue: 0, publishedAt: '2026-10-01', observedAt: '2026-10-05', hook: 'A', cta: 'same' },
  b: { views: 1000, clicks: 80, conversions: 4, revenue: 0, publishedAt: '2026-10-01', observedAt: '2026-10-05', hook: 'B', cta: 'same' },
};
let uncertainty = api.abMetricUncertainty(test);
assert.equal(uncertainty.available, true, 'valid CTR data should yield a reference interval');
assert.equal(uncertainty.includesZero, false, 'large rate difference should not include zero in this reference range');
assert(uncertainty.differenceLow > 0, 'B-A interval should be positive in this test');
assert.equal(api.abMetricUncertainty({ metric: 'ctr', a: { views: 1000, clicks: null }, b: { views: 1000, clicks: 1 } }).available, false, 'missing clicks must not be converted to zero');
let assessment = api.assessABTest(test);
assert.equal(assessment.viewsEnough, true);
assert.equal(assessment.datesMature, true);
assert.equal(assessment.qualityWarnings.length, 0, 'matching observation conditions should not trigger warnings');
test.b.observedAt = '2026-10-08';
assessment = api.assessABTest(test);
assert(assessment.qualityWarnings.some(x => x.includes('성과 확인일이 1일 넘게 차이')), 'different observation dates should trigger a warning');
test.metric = 'rpm';
assert.equal(api.abMetricUncertainty(test).available, false, 'RPM should not receive a fabricated binomial interval');
assert.equal(api.validABDate('2026-02-30'), false, 'invalid calendar date must be rejected');
console.log('A/B runtime checks: 7 passed');
