'use strict';
function catalogEntry(path,source,revision,repository='xLordTime/bots'){
 const meta={};for(const line of source.split(/\r?\n/)){const m=line.match(/^#\s*@([a-z]+):\s*(.*)$/);if(m)meta[m[1]]=m[2];}
 return {path,source,revision,name:meta.name||path.split('/').at(-1).replace(/\.txt$/,''),author:meta.author||'Deimos Community',zone:meta.zone||'',world:(meta.zone||'Eigene Bots').split('/')[0],clients:meta.clients||'',format:meta.format||'expertmode',url:`https://github.com/${repository}/blob/${revision}/${path.split('/').map(encodeURIComponent).join('/')}`};
}
async function fetchForkCatalog(fetcher=fetch){
 async function get(url){const response=await fetcher(url);if(!response.ok)throw Error(`GitHub antwortet mit ${response.status}. Bei Rate-Limit später erneut versuchen.`);return response.json();}
 const ref=await get('https://api.github.com/repos/xLordTime/bots/git/ref/heads/main');
 const revision=ref.object?.sha;if(!/^[a-f0-9]{40}$/.test(revision))throw Error('Ungültiger Fork-Commit.');
 const tree=await get(`https://api.github.com/repos/xLordTime/bots/git/trees/${revision}?recursive=1`);
 if(tree.truncated||!Array.isArray(tree.tree)||!/^\w{40}$/.test(tree.sha))throw Error('Unvollständiger Bot-Index.');
 const paths=tree.tree.filter(e=>e.type==='blob'&&e.path.startsWith('bots/')&&e.path.endsWith('.txt'));
 if(paths.length>100||paths.some(e=>e.size>65536))throw Error('Fork überschreitet die Bibliotheksgrenzen (100 Bots / 64 KB je Bot).');
 const results=[];
 for(let i=0;i<paths.length;i+=4){const batch=await Promise.all(paths.slice(i,i+4).map(async e=>{const data=await get(`https://api.github.com/repos/xLordTime/bots/git/blobs/${e.sha}`);if(data.encoding!=='base64'||typeof data.content!=='string')throw Error('Ungültige Bot-Datei.');const source=new TextDecoder().decode(Uint8Array.from(atob(data.content.replace(/\s/g,'')),c=>c.charCodeAt(0)));if(source.length>65536)throw Error('Bot zu groß.');return catalogEntry(e.path,source,revision);}));results.push(...batch);}
 return results;
}
if(typeof module!=='undefined')module.exports={catalogEntry,fetchForkCatalog};
