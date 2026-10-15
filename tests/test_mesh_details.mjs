import test from 'node:test';
import assert from 'node:assert/strict';
import {meshIdAt,locationInside,declarationsInMesh,selectionGeoJSON} from '../src/mesh-details.mjs';

test('tapped grid contains the requested geographic position',()=>{
 const id=meshIdAt(132.768,33.848,500);
 assert.ok(locationInside(id,[132.768,33.848],500));
 assert.ok(!locationInside(id,[133.1,34.1],500));
 assert.equal(selectionGeoJSON(id,500).features.length,1);
});
test('only residential-declaration records are selected',()=>{
 const a={id:1,city:'松山市',address:'松山市立花3-7-28',coord:[132.771835,33.826084]};
 const b={id:2,city:'今治市',address:'今治市北宝来町1-1',coord:[133.0,34.0]};
 const id=meshIdAt(...a.coord,500);
 assert.deepEqual(declarationsInMesh(id,500,[a,b]).map(x=>x.id),[1]);
 assert.deepEqual(declarationsInMesh(id,500,[a,b],'今治市'),[]);
});
test('selection can be cleared',()=>{
 assert.deepEqual(selectionGeoJSON(null,500),{type:'FeatureCollection',features:[]});
});
