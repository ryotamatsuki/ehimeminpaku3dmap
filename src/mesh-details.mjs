import {gridKey,polygonFromGrid} from './geo.mjs';
import {addressKey} from './names.mjs';

export function meshIdAt(lon,lat,size){
 if(!Number.isFinite(lon)||!Number.isFinite(lat))return null;
 return gridKey(lon,lat,size).join(':');
}
export function meshPolygon(id,size){
 const [i,j]=String(id).split(':').map(Number);
 if(!Number.isInteger(i)||!Number.isInteger(j))throw new Error('Invalid grid id');
 return polygonFromGrid(i,j,size);
}
export function locationInside(id,coord,size){
 if(!Array.isArray(coord)||coord.length!==2)return false;
 return meshIdAt(Number(coord[0]),Number(coord[1]),size)===id;
}
function comparable(s){
 return /\d/.test(s) && s.length>=8;
}
/** Returns three distinct categories, never claims that licensed and declared facilities are the same. */
export function inspectMesh(id,size,minpaku,permitted,coordinates,city='all'){
 const declarations=(minpaku||[]).filter(r=>(city==='all'||r.city===city));
 const declared=declarations.filter(r=>locationInside(id,r.coord,size));
 const strongNames=[],sameAddress=[],unresolvedInCity=[];
 const addresses=new Set(declared.map(r=>addressKey(r.address)).filter(comparable));
 for(const place of permitted||[]){
  if(city!=='all'&&place.city!==city)continue;
  const loc=coordinates?.[place.id];
  const positioned=loc?.precision==='street'&&locationInside(id,loc.coord,size);
  if(positioned){strongNames.push({...place,location_precision:'street'});continue}
  if(addresses.has(addressKey(place.address))){
   sameAddress.push({...place,location_precision:loc?.precision||'unresolved'});
  }
 }
 declared.sort((a,b)=>String(a.address).localeCompare(String(b.address),'ja'));
 strongNames.sort((a,b)=>String(a.name).localeCompare(String(b.name),'ja'));
 sameAddress.sort((a,b)=>String(a.name).localeCompare(String(b.name),'ja'));
 return {declared,permitted:strongNames,addressCandidates:sameAddress};
}
export function pointsGeoJSON(permitted,coordinates,city='all'){
 return {type:'FeatureCollection',features:(permitted||[]).filter(place=>city==='all'||place.city===city)
  .flatMap(place=>{
    const x=coordinates?.[place.id];
    if(x?.precision!=='street'||!Array.isArray(x.coord))return [];
    return [{type:'Feature',properties:{id:place.id,name:place.name},geometry:{type:'Point',coordinates:x.coord}}];
  })};
}
export function selectionGeoJSON(id,size){
 return {type:'FeatureCollection',features:id?[{type:'Feature',properties:{},geometry:meshPolygon(id,size)}]:[]};
}
