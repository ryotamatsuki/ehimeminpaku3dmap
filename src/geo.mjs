/** Pure geographic aggregation functions. Grid is a local equirectangular approximation, NOT JIS standard mesh. */
export const MUNICIPALITIES = [
  '四国中央市','久万高原町','新居浜市','八幡浜市','宇和島市','今治市','松山市','西条市','大洲市','伊予市',
  '西予市','東温市','上島町','松前町','砥部町','内子町','伊方町','松野町','鬼北町','愛南町'
];
export const norm = s => String(s ?? '').normalize('NFKC').replace(/[−‐‑‒–—―ーｰ]/g, '-').replace(/\s+/g, ' ').trim();
export function municipality(address) {
  const s=norm(address);
  return MUNICIPALITIES.find(name => s.includes(name)) || '市町不明';
}
export function siteKey(address) {
  const a=norm(address).replace(/^愛媛県/, '');
  const prefix=a.split(/[\s　]/)[0];
  // Remove room/building strings that immediately follow a street number.
  const matched=prefix.match(/^(.*?\d+(?:-\d+){1,4})(?=[^\d]|$)/);
  return matched?.[1] || prefix;
}
export const metricCount = (records,metric) => metric==='sites' ? new Set(records.map(r=>siteKey(r.address))).size : records.length;
const DEG_LAT=111132;
const REF_LAT=33.72;
const DEG_LON=111320*Math.cos(REF_LAT*Math.PI/180);
const ORIGIN=[132,33];
export function gridKey(lon,lat,size) {
  return [Math.floor((lon-ORIGIN[0])*DEG_LON/size),Math.floor((lat-ORIGIN[1])*DEG_LAT/size)];
}
export function polygonFromGrid(ix,iy,size) {
  return {type:'Polygon',coordinates:[[[ix,iy],[ix+1,iy],[ix+1,iy+1],[ix,iy+1],[ix,iy]].map(([x,y])=>[
    ORIGIN[0]+x*size/DEG_LON, ORIGIN[1]+y*size/DEG_LAT
  ])]};
}
export function allowedCoordinate(record, size, includeApprox=false){
  const c=record.coord;
  return Array.isArray(c) && c.length===2 && Number.isFinite(c[0]) && Number.isFinite(c[1]) &&
    c[0]>=132.0&&c[0]<=134.2&&c[1]>=32.8&&c[1]<=34.5 && (includeApprox || record.precision==='street' || size>=1000);
}
export function aggregate(records, {size=1000,metric='listings',city='all',includeApprox=false}={}){
  const filtered=records.filter(r=>(city==='all'||r.city===city));
  const positioned=filtered.filter(r=>allowedCoordinate(r,size,includeApprox));
  const cells=new Map();
  for (const r of positioned){
    const [i,j]=gridKey(r.coord[0],r.coord[1],size);const id=`${i}:${j}`;
    if(!cells.has(id))cells.set(id,{id,i,j,records:[]});
    cells.get(id).records.push(r);
  }
  const result=[...cells.values()].map(c=>({
    ...c,count:metricCount(c.records,metric),total:c.records.length,
    approx:c.records.filter(r=>r.precision!=='street').length
  }));
  result.sort((a,b)=>b.count-a.count || a.id.localeCompare(b.id));
  return {cells:result,filtered,positioned,missing:filtered.length-positioned.length};
}
export function geojson(cells,size){
  const max=Math.max(1,...cells.map(c=>c.count));
  return {type:'FeatureCollection',features:cells.map(c=>{
    const ratio=c.count/max;
    const color=ratio>=.80?'#ff725f':ratio>=.55?'#ffb65b':ratio>=.25?'#a1d69a':'#42cfd0';
    return {type:'Feature',properties:{id:c.id,count:c.count,height:25+95*Math.pow(c.count,.77),color,approx:c.approx},geometry:polygonFromGrid(c.i,c.j,size)};
  })};
}
export function cityCounts(records){
  const counts=new Map(MUNICIPALITIES.map(c=>[c,0]));
  for(const r of records)counts.set(r.city||municipality(r.address),(counts.get(r.city||municipality(r.address))||0)+1);
  return [...counts].filter(([,n])=>n>0).sort((a,b)=>b[1]-a[1]);
}
