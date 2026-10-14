
import test from 'node:test';
import assert from 'node:assert/strict';
import {filterPermits,matchingAddressCandidates,officialUrl} from '../src/names.mjs';
const p=[{name:'海の宿',city:'今治市',address:'今治市港町2-1-5'},{name:'島の宿',city:'今治市',address:'今治市港町2-1-6'}];
test('matching does not use geographic proximity',()=>{
 assert.deepEqual(matchingAddressCandidates([{address:'今治市港町2-1-5'}],p).map(x=>x.name),['海の宿']);
 assert.equal(matchingAddressCandidates([{address:'今治市港町2-1'}],p).length,0);
});
test('municipality filter and source URL allowlist',()=>{
 assert.equal(filterPermits(p,'今治市','海').length,1);
 assert.equal(officialUrl('https://example.com/hello'),null);
 assert.equal(officialUrl('javascript:alert(1)'),null);
 assert.ok(officialUrl('https://www.pref.ehime.jp/opendata-catalog/dataset/2312.html'));
});
