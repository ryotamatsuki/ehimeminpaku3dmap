
/** A different legal regime: never relabel hotels as residential minpaku. */
export const addressKey=s=>String(s||'').normalize('NFKC').replace(/^愛媛県/,'')
 .replace(/[\s　]/g,'').replace(/[−‐‑‒–—―ーｰ]/g,'-')
 .replace(/番地?/g,'-').replace(/号/g,'').replace(/-+/g,'-');
export function filterPermits(permitted,city='all',query=''){
 const q=String(query).normalize('NFKC').trim().toLowerCase();
 return permitted.filter(p=>(city==='all'||p.city===city)&&
   (!q||String(p.name+' '+p.address).normalize('NFKC').toLowerCase().includes(q)));
}
export function matchingAddressCandidates(minpaku,permits){
 const keys=new Set(minpaku.map(r=>addressKey(r.address)).filter(s=>/\d/.test(s)));
 return permits.filter(p=>keys.has(addressKey(p.address)));
}
export function officialUrl(s){
 try{const u=new URL(s);return u.protocol==='https:'&&
  ['www.pref.ehime.jp','www.city.matsuyama.ehime.jp'].includes(u.hostname)?u.href:null}
 catch{return null}
}
