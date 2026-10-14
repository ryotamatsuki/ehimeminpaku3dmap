import {MUNICIPALITIES, municipality, cityCounts, aggregate, geojson, metricCount, norm, siteKey} from './geo.mjs';
import {filterPermits,matchingAddressCandidates,officialUrl} from './names.mjs';
const $=id=>document.getElementById(id);
let records=[], permits=[], permitMeta={}, metadata={}, map=null, mapReady=false, busy=false, gridCells=new Map(), size=1000, metric='listings', city='all', includeApprox=false;
const SOURCE='https://www.pref.ehime.jp/page/57100.html';
const setText=(id,value)=>{$(id).textContent=String(value)};
function baseAddress(a){const n=norm(a).replace(/^愛媛県/,'');return siteKey(n).replace(/\s+.*$/,'')}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
const VIEW={all:{center:[132.76,33.55],zoom:8.3},松山市:{center:[132.77,33.86],zoom:11},今治市:{center:[132.99,34.07],zoom:10.3},宇和島市:{center:[132.56,33.22],zoom:10.1}};
function initMap(){
 if(typeof maplibregl==='undefined'){$('map-failed').hidden=false;return}
 const style={version:8,name:'GSI pale',sources:{gsi:{type:'raster',tiles:['https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png'],tileSize:256,attribution:'地図：国土地理院（地理院タイル）'}},layers:[{id:'background',type:'background',paint:{'background-color':'#071720'}},{id:'gsi',type:'raster',source:'gsi',paint:{'raster-opacity':.89,'raster-saturation':-.88,'raster-contrast':.17,'raster-brightness-max':.49}}]};
 try{
 map=new maplibregl.Map({container:'map',style,center:VIEW.all.center,zoom:VIEW.all.zoom,pitch:57,bearing:-18,maxPitch:75,canvasContextAttributes:{antialias:true},attributionControl:{compact:true}});
 map.addControl(new maplibregl.NavigationControl({showCompass:true,visualizePitch:true}),'top-right');
 map.on('load',()=>{
   mapReady=true;map.addSource('density',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
   map.addLayer({id:'bars',type:'fill-extrusion',source:'density',paint:{'fill-extrusion-color':['get','color'],'fill-extrusion-height':['get','height'],'fill-extrusion-base':0,'fill-extrusion-opacity':.84}});
   map.addLayer({id:'outlines',type:'line',source:'density',paint:{'line-color':'#92f3e4','line-width':.6,'line-opacity':.5}});
   map.on('click','bars',e=>{const id=e.features?.[0]?.properties?.id;if(id)showDetails(id)});
   map.on('mouseenter','bars',()=>{map.getCanvas().style.cursor='pointer'});map.on('mouseleave','bars',()=>{map.getCanvas().style.cursor='' });
   render();
 });
 map.on('error',()=>{if(!mapReady)$('map-failed').hidden=false});
 }catch(err){$('map-failed').hidden=false;console.error(err)}
}
function renderPermits(){
 const input=$('permit-search'),filtered=filterPermits(permits,city,input.value);
 setText('permit-summary',permits.length?
   '旅館業許可施設 '+filtered.length+' 件（公開名称収録 '+permits.length+' 件）':
   '公開名称を取得中、または現在利用できません');
 const box=$('permit-list');box.replaceChildren();
 for(const p of filtered.slice(0,30)){
  const wrap=document.createElement('div');wrap.className='permit-item';
  const title=document.createElement('strong');title.textContent=p.name;
  const address=document.createElement('span');address.textContent=p.address;
  wrap.append(title,address);
  const url=officialUrl(p.source_page);
  if(url){const link=document.createElement('a');link.href=url;link.target='_blank';
    link.rel='noopener noreferrer';link.textContent='出典 ↗';wrap.append(link);}
  box.append(wrap);
 }
 if(filtered.length>30){const more=document.createElement('p');more.textContent='先頭30件のみ表示。名称・住所で検索してください。';box.append(more);}
 setText('permit-note',permitMeta.warnings?.length?
   '一部の自治体データをまだ収録できていません。旅館業許可と民泊届出は別制度です。':
   '住宅宿泊事業の届出住宅とは別制度です。休廃業中の施設を含む場合があります。');
}
async function loadPermits(){
 try{
  const response=await fetch('./data/licensed_lodging.json',{cache:'no-store'});
  if(!response.ok)throw new Error('not found');
  permitMeta=await response.json();permits=Array.isArray(permitMeta.facilities)?permitMeta.facilities:[];
 }catch(e){permits=[];permitMeta={warnings:[]}}
 renderPermits();
}

function fillCitySelect(){
 const sel=$('city');sel.innerHTML='<option value="all">愛媛県全域</option>';
 for(const name of MUNICIPALITIES){const o=document.createElement('option');o.value=name;o.textContent=name;sel.append(o)}
}
function renderRanking(){
 const counts=cityCounts(records),max=counts[0]?.[1]||1;
 $('ranking').innerHTML=counts.length?counts.map(([name,n])=>`<div class="rank"><span>${escapeHtml(name)}</span><span class="n">${n.toLocaleString('ja-JP')} 件</span><div class="bar"><i style="width:${Math.max(2,100*n/max)}%"></i></div></div>`).join(''):'<p class="micro">収録データがありません。</p>';
}
function render(){
 const {cells,filtered,positioned,missing}=aggregate(records,{size,metric,city,includeApprox});
 gridCells=new Map(cells.map(c=>[c.id,c]));
 if(mapReady)map.getSource('density').setData(geojson(cells,size));
 setText('total-count',records.length.toLocaleString('ja-JP'));
 setText('visible-count',metricCount(positioned,metric).toLocaleString('ja-JP'));
 setText('city-count',cityCounts(records).length);
 setText('cell-count',cells.length);
 const txt=`表示対象 ${filtered.length} 件中、位置集計 ${positioned.length} 件 / 除外 ${missing} 件（座標なし・精度条件）`;
 setText('coverage',txt);
 setText('map-label',city==='all'?'愛媛県 民泊集中度':`${city} 民泊集中度`);
 setText('map-date',`SOURCE: EHIME PREF. / ${metadata.source_date||'DATE UNKNOWN'} / ${size}M MESH`);
 setText('source-pill',metadata.scope==='prefecture'?'県全域データ / 自動抽出・未照合':'松山市分のみ収録 / 県全域データ取込前');
 const status=metadata.scope==='prefecture'?'県全域の届出所在地をPDFから自動抽出したデータです。原本照合は未実施です。':'現行収録データは松山市の手動転記146行だけです。他市町の件数が0件という意味ではありません。';
 setText('data-warning',`${status} 座標変換に失敗した住所や低精度の代表点があり、細粒度の集中度は過信できません。`);
 $('geocode').textContent=`座標未取得の住所を検索（${records.filter(r=>!r.coord).length}件）`;
 $('details').hidden=true;
}
function showDetails(id){const c=gridCells.get(id);if(!c)return;
 $('details').hidden=false;setText('detail-count',`${c.count} ${metric==='sites'?'推定所在地':'届出住宅'}`);
 renderAddressCandidates(c.records);
 setText('detail-meta',`${size}mメッシュ / 届出住宅 ${c.total} 件 / 町域などの代表点 ${c.approx} 件を含む可能性があります。住所検索結果は実際の建物位置を保証しません。`);
}
function renderAddressCandidates(recordsInCell){
 const candidates=matchingAddressCandidates(recordsInCell,permits),node=$('detail-names');
 node.replaceChildren();
 if(!candidates.length)return;
 const heading=document.createElement('strong');
 heading.textContent='同一住所に掲載された旅館業許可施設（別制度・同一施設か未確認）';
 node.append(heading);
 for(const f of candidates.slice(0,8)){
  const line=document.createElement('p');line.textContent=f.name+'（'+f.address+'）';
  const link=document.createElement('a'),url=officialUrl(f.source_page);
  if(url){link.href=url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='出典 ↗';line.append(' ',link)}
  node.append(line);
 }
}
function flyToSelected(){if(!mapReady)return;
 if(VIEW[city])map.flyTo({...VIEW[city],pitch:56,bearing:-18,duration:900});
 else{
   const points=records.filter(r=>r.city===city&&Array.isArray(r.coord));
   if(points.length){const lons=points.map(r=>r.coord[0]),lats=points.map(r=>r.coord[1]);
     const bounds=[[Math.min(...lons)-.02,Math.min(...lats)-.02],[Math.max(...lons)+.02,Math.max(...lats)+.02]];
     map.fitBounds(bounds,{padding:60,maxZoom:12.3,duration:900});
   }
 }
}
function makeControls(){
 fillCitySelect();$('permit-search').addEventListener('input',renderPermits);$('city').addEventListener('change',e=>{city=e.target.value;flyToSelected();render();renderPermits()});
 document.querySelectorAll('[data-place]').forEach(b=>b.addEventListener('click',()=>{city=b.dataset.place;$('city').value=city;flyToSelected();render()}));
 document.querySelectorAll('[data-size]').forEach(b=>b.addEventListener('click',()=>{size=Number(b.dataset.size);document.querySelectorAll('[data-size]').forEach(x=>x.classList.toggle('selected',x===b));render()}));
 document.querySelectorAll('[data-metric]').forEach(b=>b.addEventListener('click',()=>{metric=b.dataset.metric;document.querySelectorAll('[data-metric]').forEach(x=>x.classList.toggle('selected',x===b));render()}));
 $('include-approx').addEventListener('change',e=>{includeApprox=e.target.checked;render()});
 $('geocode').addEventListener('click',geocodeMissing);$('close-detail').addEventListener('click',()=>{$('details').hidden=true});
}
function cacheRead(){try{return JSON.parse(localStorage.getItem('ehime-minpaku-geocode-v2')||'{}')}catch{return {}}}
function cacheWrite(v){try{localStorage.setItem('ehime-minpaku-geocode-v2',JSON.stringify(v))}catch{}}
function normalizeCompare(s){
 const kanji={'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10};
 const n=k=>kanji[k]??(k.startsWith('十')?10+(kanji[k.slice(1)]||0):k.endsWith('十')?(kanji[k.slice(0,-1)]||1)*10:k);
 return norm(s).replace(/^愛媛県/,'').replace(/([一二三四五六七八九十]+)丁目/g,(_,k)=>`${n(k)}-`).replace(/(\d+)丁目/g,'$1-').replace(/番地?/g,'-').replace(/号/g,'').replace(/[\s　]+/g,'').replace(/[-−‐‑‒–—―ーｰ]+/g,'-');
}
function parseGsi(features,address){
 const target=municipality(address),a=normalizeCompare(baseAddress(address));
 const opts=(Array.isArray(features)?features:[]).filter(f=>{
  const [lon,lat]=f?.geometry?.coordinates||[];
  const title=norm(f?.properties?.title);
  return Number.isFinite(lon)&&lon>=132&&lon<=134.2&&Number.isFinite(lat)&&lat>=32.8&&lat<=34.5&&title.includes(target);
 });
 if(!opts.length)return null;
 const f=opts[0],title=normalizeCompare(f.properties.title);
 // GSI often resolves only chome/town: without street-number agreement, classify as district-level.
 const numeric=a.match(/\d+(?:-\d+)+/g)||[];
 const precise=numeric.some(n=>title.includes(n));
 return {coord:f.geometry.coordinates,precision:precise?'street':'district',geocode_title:f.properties.title};
}
async function lookupGsi(q){
 const response=await fetch(`https://msearch.gsi.go.jp/address-search/AddressSearch?q=${encodeURIComponent(q)}`,{signal:AbortSignal.timeout(14000)});
 if(!response.ok)throw new Error(`GSI HTTP ${response.status}`);
 return response.json();
}
async function geocodeMissing(){
 if(busy)return;busy=true;$('geocode').disabled=true;
 const queue=records.filter(r=>!r.coord);let progress=0,hit=0;const cache=cacheRead();
 for(const r of queue){
  const addr=baseAddress(r.address);
  if(Object.hasOwn(cache,addr)){
    if(cache[addr])Object.assign(r,cache[addr]);
  }else{
   try{
    let found=parseGsi(await lookupGsi(addr),r.address);
    if(!found){const town=addr.replace(/\d.*$/,'');if(town!==addr)found=parseGsi(await lookupGsi(town),r.address)}
    cache[addr]=found;
    if(found)Object.assign(r,found);
   }catch(e){console.warn('Geocoding',addr,e);/* transient errors are not cached */}
   if(progress%10===0)cacheWrite(cache);
   await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(r.coord)hit++;
  progress++;$('progress-bar').style.width=`${100*progress/queue.length}%`;
  setText('geocode-status',`${progress}/${queue.length} 件を処理 / 今回の位置取得 ${hit} 件`);
  if(progress%10===0)render();
 }
 cacheWrite(cache);render();busy=false;$('geocode').disabled=false;
 setText('geocode-status',`完了：${queue.length}件中 ${hit}件の座標を取得。失敗・低精度の住所は分布表示から除外される場合があります。`);
}
async function load(){
 makeControls();initMap();
 try{
  const res=await fetch('./data/listings.json',{cache:'no-store'});if(!res.ok)throw new Error(`HTTP ${res.status}`);
  const payload=await res.json();metadata=payload;records=(payload.records||[]).map((r,i)=>({id:i+1,...r,city:r.city||municipality(r.address)}));
  const cache=cacheRead();for(const r of records){if(!r.coord&&cache[baseAddress(r.address)])Object.assign(r,cache[baseAddress(r.address)])}
  renderRanking();render();renderPermits();
  setText('geocode-status',`読込完了：${records.length}件。座標あり ${records.filter(r=>r.coord).length}件。未取得の住所はボタンで変換できます。`);
 }catch(e){setText('geocode-status',`データ読み込み失敗：${e.message}。ローカル起動は python -m http.server を利用してください。`)}
}
load();
loadPermits();
