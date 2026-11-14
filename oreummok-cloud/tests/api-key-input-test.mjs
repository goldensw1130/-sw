import test from 'node:test';import assert from 'node:assert/strict';import {normalizeApiKey} from '../service/assistant-config.mjs';
const sample='AIza_QA_SAMPLE_NOT_A_REAL_KEY_1234567890';
test('API key paste normalization accepts normal keys, invisible clipboard characters, quotes and assignment labels',()=>{for(const raw of [sample,' '+sample+'\n','\ufeff'+sample+'\u200b','GEMINI_API_KEY="'+sample+'"','GOOGLE_API_KEY = ‘'+sample+'’',sample.slice(0,10)+'\u00a0\r\n'+sample.slice(10)])assert.equal(normalizeApiKey(raw),sample);});
test('API input does not assume token alphabet or a 200-character ceiling',()=>{assert.equal(normalizeApiKey('Q'.repeat(250)+'+/=.'),'Q'.repeat(250)+'+/=.');});
test('bad API paste is rejected without echoing any secret',()=>{for(const raw of ['short','한글설명'+sample,'x'.repeat(4097),'"'+sample])assert.throws(()=>normalizeApiKey(raw),e=>!e.message.includes(sample));});
