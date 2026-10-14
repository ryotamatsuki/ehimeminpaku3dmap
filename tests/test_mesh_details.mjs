import test from 'node:test';
import assert from 'node:assert/strict';
import {meshIdAt,locationInside,inspectMesh,pointsGeoJSON,selectionGeoJSON} from '../src/mesh-details.mjs';
test('grid boundaries: tapping anywhere in the same cell gives same id',()=>{
 const id=meshIdAt(132.768,33.848,500);
 assert.ok(locationInside(id,[132.768,33.848],500));
 assert.ok(!locationInside(id,[133.1,34.1],500));
 assert.equal(selectionGeoJSON(id,500).features.length,1);
});
test('declared, named, and same-address possible match remain legally separated',()=>{
 const addr='松山市立花3-7-28';
 const id=meshIdAt(132.771835,33.826084,500);
 const declarations=[{id:1,address:addr,city:'松山市',coord:[132.771835,33.826084],precision:'street'}];
 const permits=[
  {id:'p1',name:'A旅館',address:addr,city:'松山市'},
  {id:'p2',name:'B旅館',address:'松山市立花3-7-29',city:'松山市'},
  {id:'p3',name:'C旅館',address:'松山市立花3-7-28',city:'松山市'},
  {id:'p4',name:'D旅館',address:'今治市北宝来町1-1-1',city:'今治市'}
 ];
 const coords={
  p1:{coord:[132.771835,33.826084],precision:'street'},
  p2:{coord:[132.77180,33.82608],precision:'district'},
  p3:{coord:null,precision:'unresolved'},
  p4:{coord:[132.77182,33.82608],precision:'street'}
 };
 const result=inspectMesh(id,500,declarations,permits,coords,'松山市');
 assert.equal(result.declared.length,1);
 assert.deepEqual(result.permitted.map(x=>x.id),['p1']);
 assert.deepEqual(result.addressCandidates.map(x=>x.id),['p3']);
 assert.equal(pointsGeoJSON(permits,coords,'松山市').features.length,1);
});
test('unknown names are not silently joined by shared location coordinates',()=>{
 const id=meshIdAt(132.77,33.82,1000);
 const res=inspectMesh(id,1000,[{address:'松山市立花3-7-28',city:'松山市',coord:[132.77,33.82]}],
  [{id:'x',name:'旅館X',city:'松山市',address:'松山市立花3-7-29'}],{'x':{precision:'district',coord:[132.77,33.82]}},'松山市');
 assert.equal(res.permitted.length,0);
 assert.equal(res.addressCandidates.length,0);
});
