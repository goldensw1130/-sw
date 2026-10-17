'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(__dirname + '/ShortsCompass.html', 'utf8');
const start = html.indexOf('function youtubeNumber(value)');
const end = html.indexOf('async function youtubeLiveSearch()', start);
if (start < 0 || end < 0) throw new Error('Could not find YouTube sort helpers.');
const sandbox = { Date, Number, String, Map, Math, Array };
vm.createContext(sandbox);
const helpers = html.slice(start, end);
vm.runInContext(helpers + '\nthis.api={youtubeNumber,youtubeViewsPerDay,sortYouTubeDetails};', sandbox);
const api = sandbox.api;
const fixedNow = Date.parse('2026-10-17T00:00:00Z');
const item = (id, views, published) => ({
  id,
  statistics: { viewCount: views },
  snippet: { publishedAt: published, title: id }
});

// videos.list response order is deliberately reversed; actual viewCount must control ranking.
let sorted = api.sortYouTubeDetails([
  item('low', 200, '2026-10-15T00:00:00Z'),
  item('high', 9000, '2026-10-10T00:00:00Z'),
  item('mid', 1000, '2026-10-16T00:00:00Z')
], ['high', 'mid', 'low'], 'viewCount', fixedNow);
assert.deepEqual(Array.from(sorted, x => x.id), ['high', 'mid', 'low']);

// Velocity ranking finds the newer fast-growing sample, not the highest lifetime count.
sorted = api.sortYouTubeDetails([
  item('old', 1000000, '2026-07-17T00:00:00Z'),
  item('fast', 300000, '2026-10-16T00:00:00Z'),
  item('slow', 50000, '2026-10-15T00:00:00Z')
], ['old', 'slow', 'fast'], 'velocity', fixedNow);
assert.deepEqual(Array.from(sorted, x => x.id), ['fast', 'slow', 'old']);

// Date mode is descending even when detail response order differs.
sorted = api.sortYouTubeDetails([
  item('older', 10, '2026-10-01T00:00:00Z'),
  item('newer', 10, '2026-10-16T00:00:00Z')
], ['newer', 'older'], 'date', fixedNow);
assert.deepEqual(Array.from(sorted, x => x.id), ['newer', 'older']);

// Relevance/rating preserve the original search.list ordering after the detail request.
sorted = api.sortYouTubeDetails([
  item('third', 5, '2026-10-01T00:00:00Z'),
  item('first', 10, '2026-10-01T00:00:00Z'),
  item('second', 7, '2026-10-01T00:00:00Z')
], ['first', 'second', 'third'], 'relevance', fixedNow);
assert.deepEqual(Array.from(sorted, x => x.id), ['first', 'second', 'third']);

// Missing view metrics and invalid dates must not crash or outrank known numeric data.
sorted = api.sortYouTubeDetails([
  { id: 'unknown', statistics: {}, snippet: { publishedAt: 'not-a-date' } },
  item('known', 0, '2026-10-16T00:00:00Z')
], ['unknown', 'known'], 'viewCount', fixedNow);
assert.deepEqual(Array.from(sorted, x => x.id), ['known', 'unknown']);
assert.equal(api.youtubeViewsPerDay({ statistics: {}, snippet: {} }, fixedNow), null);
assert.equal(api.youtubeNumber('12,345'), 12345);
assert.equal(api.youtubeNumber(null), null);

async function integrationSearch(sortMode, searchIds, details) {
  const out = { innerHTML: '', querySelector: () => null };
  const button = { disabled: false };
  const values = {
    apiQuery: { value: 'example topic' },
    apiMax: { value: '10' },
    apiOrder: { value: sortMode },
    liveSearchResults: out,
  };
  const calls = [];
  const document = {
    getElementById: id => values[id] || null,
    querySelector: () => button,
  };
  const fetch = async url => {
    calls.push(String(url));
    if (String(url).includes('/youtube/v3/search?')) {
      return { ok: true, json: async () => ({ items: searchIds.map(id => ({ id: { videoId: id } })) }) };
    }
    return { ok: true, json: async () => ({ items: details }) };
  };
  const sandbox = { Date, Number, String, Map, Math, Array, JSON, document, fetch, ytKey: () => 'test-key', esc: x => String(x ?? ''), alert: () => {} };
  vm.createContext(sandbox);
  const full = html.slice(html.indexOf('let currentYouTubeSearchResults=[];'), html.indexOf('function saveApiResult(x)'));
  vm.runInContext(full + '\nthis.testApi={youtubeLiveSearch};', sandbox);
  await sandbox.testApi.youtubeLiveSearch();
  return { html: out.innerHTML, calls, button };
}

(async () => {
  const now = Date.now();
  const stamp = ms => new Date(now - ms * 86400000).toISOString();
  let result = await integrationSearch('viewCount', ['high', 'low'], [
    { id: 'low', statistics: { viewCount: 100 }, snippet: { title: 'Low title', channelTitle: 'Channel L', publishedAt: stamp(1), description: '' } },
    { id: 'high', statistics: { viewCount: 100000 }, snippet: { title: 'High title', channelTitle: 'Channel H', publishedAt: stamp(10), description: '' } },
  ]);
  assert(result.html.indexOf('High title') < result.html.indexOf('Low title'), 'full search flow should display the highest-view result first');
  assert(result.html.includes('실제 조회수로 내림차순'), 'full search flow should explain the actual metric used');
  assert.equal(result.button.disabled, false, 'search button should be re-enabled after response');

  result = await integrationSearch('velocity', ['old', 'fast', 'slow'], [
    { id: 'old', statistics: { viewCount: 1000000 }, snippet: { title: 'Old title', channelTitle: 'Old channel', publishedAt: stamp(90), description: '' } },
    { id: 'fast', statistics: { viewCount: 300000 }, snippet: { title: 'Fast title', channelTitle: 'Fast channel', publishedAt: stamp(1), description: '' } },
    { id: 'slow', statistics: { viewCount: 50000 }, snippet: { title: 'Slow title', channelTitle: 'Slow channel', publishedAt: stamp(2), description: '' } },
  ]);
  assert(result.html.indexOf('Fast title') < result.html.indexOf('Slow title') && result.html.indexOf('Slow title') < result.html.indexOf('Old title'), 'full search flow should rank within-sample estimated views/day');
  assert(result.calls[0].includes('order=date'), 'velocity mode must request recent/date-ordered sample before local ranking');
  assert(result.html.includes('최근 24시간 증가량이 아닙니다'), 'velocity mode must disclose estimate limitation');
  assert.equal(result.button.disabled, false, 'search button should be re-enabled after velocity ranking');
  console.log('YouTube ranking runtime assertions: 15 passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
