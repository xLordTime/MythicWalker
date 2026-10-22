'use strict';
function soundB64(bytes){let s='';for(let i=0;i<bytes.length;i+=0x8000)s+=String.fromCharCode(...bytes.subarray(i,i+0x8000));return btoa(s);}
function soundBytes(value){return Uint8Array.from(atob(value),c=>c.charCodeAt(0));}
function soundPcm(buffer){
 const channels=buffer.numberOfChannels,frames=buffer.length,rate=buffer.sampleRate;
 if(![1,2].includes(channels)||frames/rate>15||frames<=0)throw Error('Kurzer Effekt mit maximal 15 Sekunden und 1–2 Kanälen erforderlich.');
 const size=frames*channels*2;if(size+44>3*1024*1024)throw Error('WAV wäre größer als 3 MB. Kürzeren Sound wählen.');
 const bytes=new Uint8Array(44+size),v=new DataView(bytes.buffer),word=(p,s)=>{for(let i=0;i<s.length;i++)bytes[p+i]=s.charCodeAt(i);};
 word(0,'RIFF');v.setUint32(4,36+size,true);word(8,'WAVE');word(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,channels,true);v.setUint32(24,rate,true);v.setUint32(28,rate*channels*2,true);v.setUint16(32,channels*2,true);v.setUint16(34,16,true);word(36,'data');v.setUint32(40,size,true);
 const data=Array.from({length:channels},(_,c)=>buffer.getChannelData(c));let at=44;
 for(let f=0;f<frames;f++)for(let c=0;c<channels;c++){const sample=Math.max(-1,Math.min(1,data[c][f]||0));v.setInt16(at,Math.round(sample*(sample<0?32768:32767)),true);at+=2;}
 return bytes;
}
function createSounds({state,command,toast,esc}){
 const $=s=>document.getElementById('sound-'+s);let active=false,connected=false,busy=false,working=false,uncertain=false,generation=0,offset=0,total=0,rows=[],selection=null,original=null,replacement=null,upload=null,timer=null,jobId=0,handledJob=0,originalUrl=null,newUrl=null;
 const ready=()=>state.connected&&!state.demo&&!state.bridgeDemo&&state.soundAvailable;
 const revoke=()=>{for(const u of [originalUrl,newUrl])if(u)URL.revokeObjectURL(u);originalUrl=newUrl=null;};
 function controls(){
  const ok=ready()&&!busy&&!working&&!uncertain;
  for(const id of ['detect','configure','load','search-button','archive','query','path'])$(id).disabled=!ok;
  $('prev').disabled=!ok||offset===0;$('next').disabled=!ok||offset+120>=total;
  $('preset').disabled=!ok||!original;$('file').disabled=!ok||!original;
  $('apply').disabled=!ok||!original||!replacement||!$('confirm').checked;
  $('restore').disabled=!ok||!original||!selection?.changed||!$('confirm').checked;
  $('check').disabled=!ready()||busy;
  $('mode').textContent=!state.connected?'Bridge offline':!state.soundAvailable?'Bridge ab Beta 17 erforderlich':working?'Dateioperation läuft':uncertain?'Status prüfen':'Lokale Dateizentrale';
 }
 function clearSelection(){generation++;selection=original=replacement=null;upload=null;$('file').value='';$('confirm').checked=false;revoke();$('original').removeAttribute('src');$('replacement').removeAttribute('src');$('selection').textContent='Wähle einen Sound aus der Liste.';$('replacement-info').textContent='Deine Aufnahme oder eine eigene Datei auswählen.';controls();}
 function setArchives(data){
  clearSelection();$('path').value=data.installation||'';const previous=$('archive').value;
  $('archive').innerHTML='<option value="">Archiv auswählen …</option>'+(data.archives||[]).map(a=>`<option value="${esc(a.id)}">${esc(a.id)} · ${(a.bytes/1048576).toFixed(1)} MB</option>`).join('');
  $('archive').value=(data.archives||[]).some(a=>a.id===previous)?previous:(data.archives||[]).find(a=>/sound-worlddata\.wad/i.test(a.id))?.id||(data.archives||[]).find(a=>/sound/i.test(a.id))?.id||'';
  $('status').textContent=data.archives?.length?`${data.archives.length} Archive gefunden. Wähle ein Sound-Archiv und lade die Liste.`:'Installation auswählen. Der Ordner muss Bin und Data/GameData enthalten.';
  rows=[];total=0;drawRows();
 }
 async function run(fn){if(busy||!ready())return;busy=true;controls();try{return await fn();}catch(e){toast(e.message);$('status').textContent=e.message;}finally{busy=false;controls();}}
 function drawRows(){
  $('count').textContent=`${total?offset+1:0}–${Math.min(offset+120,total)} von ${total} Sounds`;
  $('list').innerHTML=rows.length?rows.map((r,i)=>`<button class="sound-row ${selection?.name===r.name?'selected':''}" data-sound-row="${i}" ${working||uncertain?'disabled':''}><span class="sound-file-icon">♪</span><span><strong>${esc(r.name)}</strong><small>${esc(r.format.toUpperCase())} · ${(r.bytes/1024).toFixed(1)} KB${r.candidate?' · Trefferlaut-Kandidat':''}${r.changed?' · Geändert'+(r.label?' · '+esc(r.label):''):''}${r.format==='mp3'?' · Austausch noch nicht unterstützt':''}</small></span><span>${r.changed?'↺':'›'}</span></button>`).join(''):'<div class="empty-state">Noch keine Sounds. Archiv wählen und „Sounds laden“ drücken.</div>';
  document.querySelectorAll('[data-sound-row]').forEach(b=>b.onclick=()=>run(()=>select(rows[Number(b.dataset.soundRow)])));
  controls();
 }
 async function list(reset=true){
  if(working||uncertain)throw Error('Dateioperation zuerst abschließen oder Status prüfen.');
  if(reset)offset=0;clearSelection();const archive=$('archive').value;if(!archive)throw Error('Archiv auswählen.');
  const result=await command('sound_files',{archive,query:$('query').value.trim(),offset});rows=result.files;total=result.total;
  $('status').textContent=`${result.changes} Änderungen in diesem Archiv. Dateinamen sind Suchhinweise; Original immer vorhören.`;
  $('backup').textContent=result.backup?'Sicherung: '+result.backup:'Beim ersten Austausch wird eine vollständige Originalsicherung angelegt.';drawRows();
 }
 async function select(row){
  if(working||uncertain)return;clearSelection();selection={...row,archive:$('archive').value};const version=generation;
  $('selection').textContent=row.name;drawRows();
  const result=await command('sound_inspect',{archive:selection.archive,name:row.name});if(version!==generation||!ready())return;
  original=result;originalUrl=URL.createObjectURL(new Blob([soundBytes(result.data)],{type:result.format==='wav'?'audio/wav':'audio/ogg'}));$('original').src=originalUrl;
  $('selection').textContent=`${row.name}\n${result.duration}s · ${result.rate} Hz · ${result.channels} Kanal/Kanäle · ${result.format.toUpperCase()}`;
  $('replacement-info').textContent='Original vorhören. Danach deinen Schadenssound oder eine eigene Datei zuweisen.';
  controls();
 }
 async function prepare(bytes,name){
  const version=generation,info=original;if(!info)throw Error('Zuerst Original auswählen.');
  if(bytes.byteLength>6*1024*1024)throw Error('Quelldatei zu groß (max. 6 MB).');
  let output;
  if(info.format==='ogg'){
   const raw=new Uint8Array(bytes);if(String.fromCharCode(...raw.slice(0,4))!=='OggS'||!new TextDecoder('latin1').decode(raw.slice(0,100)).includes('vorbis'))throw Error('Für dieses Ziel wird Ogg-Vorbis benötigt. Der hinterlegte Schadenssound enthält diese Version; eigene OGA/Opus-Dateien vorher konvertieren.');
   if(raw.length>3*1024*1024)throw Error('Maximal 3 MB.');output=raw;
  }else{
   const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio||!window.OfflineAudioContext)throw Error('Audiokonvertierung wird von diesem Browser nicht unterstützt.');
   const ctx=new Audio();let decoded;try{decoded=await ctx.decodeAudioData(bytes.slice(0));}finally{await ctx.close();}
   if(decoded.duration>15)throw Error('Aufnahme zu lang. Maximal 15 Sekunden pro Effekt.');
   const offline=new OfflineAudioContext(info.channels,Math.ceil(decoded.duration*info.rate),info.rate),source=offline.createBufferSource();source.buffer=decoded;source.connect(offline.destination);source.start();output=soundPcm(await offline.startRendering());
  }
  if(version!==generation||!ready())return;
  replacement={data:soundB64(output),name};if(newUrl)URL.revokeObjectURL(newUrl);newUrl=URL.createObjectURL(new Blob([output],{type:info.format==='wav'?'audio/wav':'audio/ogg'}));$('replacement').src=newUrl;
  $('replacement-info').textContent=`${name} · ${info.format.toUpperCase()} · ${(output.length/1024).toFixed(1)} KB. Prüfsummen und Format werden vor dem Schreiben erneut geprüft.`;controls();
 }
 async function status(){
  const result=await command('sound_status');working=Boolean(result.running);uncertain=false;
  if(result.id)jobId=result.id;$('status').textContent=result.message||'Bereit.';
  if(result.result?.backup)$('backup').textContent='Sicherung: '+result.result.backup;
  if(!working&&jobId&&jobId!==handledJob){handledJob=jobId;jobId=0;clearSelection();if(result.error)toast(result.error);else if(result.result)toast(result.message);if($('archive').value)await list(false);$('status').textContent=result.message;}
  controls();drawRows();schedule();return result;
 }
 function schedule(){clearTimeout(timer);timer=null;if(ready()&&(active||working||uncertain))timer=setTimeout(()=>{timer=null;poll();},2000);}
 async function poll(){if(!ready()||busy){schedule();return;}try{await status();}catch(e){uncertain=true;$('status').textContent='Status unklar: '+e.message+' Nicht erneut anwenden; Status prüfen.';controls();schedule();}}
 async function change(restore){
  if(!original||!selection||!$('confirm').checked)throw Error('Original auswählen und geschlossene Spielclients bestätigen.');
  if(!restore&&!replacement)throw Error('Ersatzsound auswählen.');
  uncertain=true;controls();
  try{const result=await command(restore?'sound_restore':'sound_apply',{archive:selection.archive,name:selection.name,expected:original.sha256,label:$('label').value.trim(),...(!restore?{data:replacement.data}:{})});working=Boolean(result.started);jobId=result.id;uncertain=false;$('status').textContent='Operation läuft lokal. Fortschritt wird abgefragt.';}catch(e){$('status').textContent=e.message+' Status prüfen, bevor du erneut anwendest.';toast(e.message);}finally{drawRows();schedule();}
 }
 $('detect').onclick=()=>run(async()=>{const result=await command('sound_detect');const paths=Object.entries(result.paths||{});$('installations').innerHTML=paths.map(([region,path])=>`<option value="${esc(path)}">${esc(region.toUpperCase())}</option>`).join('');if(paths.length){$('path').value=(result.paths.de||paths[0][1]);$('status').textContent='Installation erkannt. Pfad prüfen und „Ordner verwenden“ drücken.';}else $('status').textContent='Keine Installation automatisch erkannt. Pfad manuell eintragen.';});
 $('configure').onclick=()=>run(async()=>setArchives(await command('sound_config',{path:$('path').value.trim()})));
 $('load').onclick=$('search-button').onclick=()=>run(()=>list());$('query').onkeydown=e=>{if(e.key==='Enter')run(()=>list());};
 $('archive').onchange=()=>{rows=[];total=0;offset=0;clearSelection();drawRows();};
 $('prev').onclick=()=>run(()=>{offset=Math.max(0,offset-120);return list(false);});$('next').onclick=()=>run(()=>{offset+=120;return list(false);});
 $('preset').onclick=()=>run(async()=>{if(!original)return;const response=await fetch(`assets/sounds/damage.${original.format}`);if(!response.ok)throw Error('Voreinstellung nicht geladen. Seite neu laden.');$('label').value='Schaden bekommen';await prepare(await response.arrayBuffer(),'Dein Sound · Schaden bekommen');});
 $('file').onchange=()=>run(async()=>{upload=$('file').files[0];if(upload){if(upload.size>6*1024*1024)throw Error('Datei zu groß (max. 6 MB).');await prepare(await upload.arrayBuffer(),upload.name);}});
 $('confirm').onchange=controls;$('apply').onclick=()=>run(()=>change(false));$('restore').onclick=()=>run(()=>change(true));$('check').onclick=()=>run(status);
 async function init(){await status();if(!working)setArchives(await command('sound_archives'));schedule();}
 controls();
 return {render(){const ok=ready();if(ok&&!connected){connected=true;if(active)run(init);}else if(!ok&&connected){connected=false;clearTimeout(timer);timer=null;clearSelection();rows=[];total=0;working=false;uncertain=true;jobId=handledJob=0;drawRows();}controls();},navigate(page){active=page==='sound';if(active&&ready())run(init);else if(!working){clearTimeout(timer);timer=null;}},closed(){connected=false;working=false;uncertain=true;jobId=handledJob=0;clearTimeout(timer);timer=null;clearSelection();rows=[];total=0;drawRows();}};
}
if(typeof module!=='undefined')module.exports={soundPcm,createSounds};
