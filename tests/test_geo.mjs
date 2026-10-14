import {test} from 'node:test';import assert from 'node:assert/strict';
import {municipality,siteKey,aggregate,geojson,cityCounts} from '../src/geo.mjs';
test('recognizes all 20 municipalities and county-prefixed towns',()=>{
 assert.equal(municipality('今治市大三島町宮浦100'),'今治市');
 assert.equal(municipality('北宇和郡松野町大字松丸244'),'松野町');
 assert.equal(municipality('南宇和郡愛南町御荘平城1'),'愛南町');
});
test('distinct rooms of one street address share a site key',()=>{
 assert.equal(siteKey('松山市道後町２－１０－３３ Ｔ’ｓマンション２ 202'),siteKey('松山市道後町２－１０－３３ Ｔ’ｓマンション２ 306'));
});
test('aggregation retains duplicate homes but collapses approximate sites',()=>{
 const r=[{address:'松山市道後町2-10-33 202',city:'松山市',coord:[132.79,33.86],precision:'street'},
 {address:'松山市道後町2-10-33 306',city:'松山市',coord:[132.79,33.86],precision:'street'},
 {address:'今治市大三島町宮浦1',city:'今治市',coord:[133.07,34.25],precision:'district'}];
 let a=aggregate(r,{size:500,city:'松山市',metric:'listings'});assert.equal(a.cells[0].count,2);
 a=aggregate(r,{size:500,city:'松山市',metric:'sites'});assert.equal(a.cells[0].count,1);
 a=aggregate(r,{size:500,city:'all'});assert.equal(a.positioned.length,2);
 a=aggregate(r,{size:1000,city:'all'});assert.equal(a.positioned.length,3);
 assert.equal(geojson(a.cells,1000).features.length,2);
 assert.equal(cityCounts(r)[0][1],2);
});
