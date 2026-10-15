import {gridKey,polygonFromGrid} from './geo.mjs';
/** Only geometry and prefectural residential-accommodation declaration selection. */
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
export function declarationsInMesh(id,size,records,city='all'){
 return (records||[]).filter(r=>(city==='all'||r.city===city)&&locationInside(id,r.coord,size))
 .sort((a,b)=>String(a.address).localeCompare(String(b.address),'ja'));
}
export function selectionGeoJSON(id,size){
 return {type:'FeatureCollection',features:id?[{type:'Feature',properties:{},geometry:meshPolygon(id,size)}]:[]};
}
