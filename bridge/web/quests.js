'use strict';
const questEscape=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function validateQuestPlan(value){
 if(!value||value.version!==1||!Array.isArray(value.quests)||value.quests.length>2000)throw Error('Questplan: Version 1 und maximal 2.000 Einträge erforderlich.');
 const seen=new Set(),str=(v,n)=>typeof v==='string'?v.trim().slice(0,n):'';
 const quests=value.quests.map(q=>{
  if(!q||typeof q.id!=='string'||!/^\d{1,20}$/.test(q.id)||!str(q.name,200)||q.goal_id!=null&&(typeof q.goal_id!=='string'||!/^\d{1,20}$/.test(q.goal_id)))throw Error('Jede Quest benötigt eine numerische ID als Text und einen Namen. Teilziel-ID ist optional.');
  const row={id:q.id,goal_id:q.goal_id||null,name:str(q.name,200),world:str(q.world,120),area:str(q.area,120),note:str(q.note,500)};
  const key=row.id+':'+(row.goal_id||'*');if(seen.has(key))throw Error('Doppelte Quest-/Teilziel-ID im Plan.');seen.add(key);return row;
 });
 return {version:1,name:str(value.name,120)||'Mein Questplan',quests};
}
function questMatch(rows,snapshot){
 if(snapshot?.status!=='ready'||!snapshot.active_id)return -1;
 let matches=rows.map((r,i)=>({r,i})).filter(({r})=>r.id===snapshot.active_id);
 const precise=matches.filter(({r})=>r.goal_id&&r.goal_id===snapshot.goal_id);
 matches=precise.length?precise:matches.filter(({r})=>!r.goal_id);
 return matches.length===1?matches[0].i:-1;
}
function createQuests({state,command,toast,download}){
 const $=suffix=>document.getElementById('quests-'+suffix),escape=questEscape;
 let plan={version:1,name:'Mein Questplan',quests:[]},snapshot=null,message='Verbinde die Bridge und wähle einen gehookten Client.',active=false,pending=false,timer=null,generation=0,clientId='',eligibility='',popup=null,stamp='',lastFocus='';
 try{const raw=localStorage.getItem('mythic-quest-plan-v1');if(raw)plan=validateQuestPlan(JSON.parse(raw));}catch{toast('Gespeicherten Questplan nicht lesbar. Bitte erneut importieren.');}
 const picker=createAccountPicker({prefix:'quests',state,command,toast,beforeChange:async()=>{reset();}});
 const live=()=>state.connected&&!state.demo&&!state.bridgeDemo&&state.questAvailable;
 const eligible=()=>live()&&state.clients.some(c=>c.id===picker.ids()[0]&&c.hooked);
 const watching=()=>active||popup&&!popup.closed;
 function save(){try{localStorage.setItem('mythic-quest-plan-v1',JSON.stringify(plan));}catch{toast('Plan konnte nicht gespeichert werden. Export nutzen.');}}
 function reset(){generation++;snapshot=null;stamp='';lastFocus='';message='Questdaten werden neu gelesen …';clearTimeout(timer);timer=null;draw();}
 function current(){return snapshot?.status==='ready'?snapshot.quests.find(q=>q.id===snapshot.active_id):null;}
 function overlayHtml(){const q=current(),client=state.clients.find(c=>c.id===clientId);return `<div class="quest-overlay-head"><span class="chip">${q?'LIVE · QUEST':'QUEST-TRACKER'}</span><small>${escape(client?.title||'')} · ${escape(stamp)}</small></div><h2>${escape(q?.name||'Keine aktuelle Quest')}</h2><p>${escape(q?snapshot.goal_text||q.goals?.find(g=>g.id===snapshot.goal_id)?.name||'Teilzieltext derzeit nicht verfügbar.':message)}</p><small>${escape(q?`${snapshot.zone} · Quest ${q.id} / Ziel ${snapshot.goal_id}`:'Wähle einen Client im Tab Questen.')}</small>`;}
 function drawOverlay(){
  $('current').innerHTML=overlayHtml();
  try{if(popup&&!popup.closed){popup.document.getElementById('quest-popup-content').innerHTML=overlayHtml();}}catch{popup=null;}
 }
 function draw(){
  $('status').textContent=message;$('refresh').disabled=!eligible()||pending;$('add').disabled=!current();
  drawOverlay();
  const mode=$('view').value||'journal',rows=mode==='plan'?plan.quests:snapshot?.quests||[];
  const match=questMatch(rows,snapshot),query=$('search').value.trim().toLocaleLowerCase('de'),world=$('world').value,main=$('mainline').checked;
  const worlds=[...new Set(rows.map(r=>r.world||'Unbekannt'))].sort();
  $('world').innerHTML='<option value="">Alle Welten</option>'+worlds.map(w=>`<option value="${escape(w)}">${escape(w)}</option>`).join('');$('world').value=worlds.includes(world)?world:'';
  let count=0,lastArea='',html='';
  rows.forEach((q,i)=>{
   const selected=i===match,w=q.world||'Unbekannt';
   if(!selected&&((query&&!`${q.name} ${q.id} ${q.note||''}`.toLocaleLowerCase('de').includes(query))||($('world').value&&w!==$('world').value)||(mode==='journal'&&main&&q.mainline!==true)))return;
   count++;const area=q.area||w;
   if(area!==lastArea){html+=`<h3 class="quest-area">${escape(area)}</h3>`;lastArea=area;}
   html+=`<article class="quest-row ${selected?'current':''}" ${selected?'id="quests-highlight" aria-current="step"':''}><span class="quest-number">${mode==='plan'?i+1:'◇'}</span><div><div class="quest-row-title"><strong>${escape(q.name)}</strong>${selected?'<span class="chip quest-active">Aktuell</span>':''}${q.mainline===true?'<span class="chip">Hauptquest</span>':''}${q.ready===true?'<span class="chip">Abgabebereit</span>':''}</div><small>Quest ${escape(q.id)}${q.goal_id?' · Teilziel '+escape(q.goal_id):''}${q.language==='key'?' · Übersetzung nicht verfügbar':''}</small>${q.note?`<p>${escape(q.note)}</p>`:''}${selected?`<ol class="quest-goals">${(q.goals||current()?.goals||[]).map(g=>`<li class="${g.id===snapshot.goal_id?'current':''}">${escape(g.id===snapshot.goal_id&&snapshot.goal_text?snapshot.goal_text:g.name)}${g.id===snapshot.goal_id?' <span>← Aktives Ziel</span>':''}</li>`).join('')}</ol>`:''}</div></article>`;
  });
  $('list').innerHTML=html||'<div class="empty-state">'+(mode==='plan'?'Noch kein Questplan. Aktuelle Quest hinzufügen oder einen eigenen Plan importieren.':'Noch keine Questdaten. Client auswählen, hooken und im Spiel eine Quest verfolgen.')+'</div>';
  $('count').textContent=`${count} angezeigt · ${rows.length} ${mode==='plan'?'Planschritte':'Quests im Journal'}`;
  $('plan-name').textContent=plan.name;
  $('plan-note').textContent=mode==='plan'&&current()&&match<0?'Aktuelle Quest ist nicht eindeutig im Plan enthalten. Die Live-Karte bleibt aktuell.':mode==='journal'?'Das Spieljournal enthält angenommene Quests. Es ist keine vollständige Welt-Questreihe.':'Die Reihenfolge stammt aus deinem Plan. Ein Questwechsel bestätigt keinen Abschluss.';
  const focus=snapshot?`${clientId}:${snapshot.active_id}:${snapshot.goal_id}:${mode}`:'';
  if(active&&$('follow').checked&&match>=0&&focus!==lastFocus){lastFocus=focus;const el=document.getElementById('quests-highlight');if(el?.scrollIntoView)el.scrollIntoView({block:'nearest',behavior:'auto'});}
 }
 function schedule(){clearTimeout(timer);timer=null;if(watching()&&eligible())timer=setTimeout(()=>{timer=null;refresh();},3000);}
 async function refresh(){
  if(pending||!eligible()||!watching())return;
  pending=true;const version=generation,id=picker.ids()[0];draw();
  try{
   const data=await command('quest_status',{ids:[id]});
   if(version!==generation||picker.ids()[0]!==id||!eligible())return;
   if(data?.id!==id||!Array.isArray(data.quests))throw Error('Ungültige Quest-Antwort. Bridge aktualisieren.');
   snapshot=data;stamp=new Date().toLocaleTimeString('de-DE');
   message={ready:'Live · Folgt der im Spiel ausgewählten Quest.',loading:'Zonenwechsel · Warte auf das Spiel …',transition:'Questwechsel · Lese erneut …',no_active:'Im Spiel ist keine Quest ausgewählt.'}[data.status]||'Queststatus derzeit nicht verfügbar.';
   if(data.truncated)message+=' Journal aus Zeit-/Größengründen gekürzt.';if(data.metadata_available===false)message+=' Questdetails nicht vollständig lesbar; Zuordnung per ID bleibt verfügbar.';
  }catch(e){if(version===generation){snapshot=null;stamp='';message='Questdaten nicht verfügbar: '+(e.message||'Lesezeitlimit erreicht.');}}
  finally{pending=false;draw();schedule();}
 }
 function render(){
  picker.render();const id=picker.ids()[0]||'';
  const key=`${state.connected}:${state.questAvailable}:${id}:${eligible()}`;if(key!==eligibility){eligibility=key;clientId=id;reset();}
  if(!eligible()){
   if(snapshot)reset();clearTimeout(timer);timer=null;
   message=!state.connected?'Zuerst die lokale Bridge verbinden.':state.demo||state.bridgeDemo?'Quest-Tracking benötigt einen echten Spielclient.':!state.questAvailable?'Bridge auf Beta 16 oder neuer aktualisieren.':'Client auswählen und hooken.';
   draw();return;
  }
  if(watching()&&!pending&&!timer)refresh();
 }
 for(const id of ['view','world','mainline','follow'])$(id).onchange=()=>{lastFocus='';draw();};$('search').oninput=draw;
 $('refresh').onclick=refresh;
 $('add').onclick=()=>{const q=current();if(!q)return;try{plan=validateQuestPlan({...plan,quests:[...plan.quests,{id:q.id,goal_id:snapshot.goal_id,name:q.name,world:snapshot.zone.split('/')[0],area:snapshot.zone,note:snapshot.goal_text}]});save();$('view').value='plan';draw();toast('Aktuelles Teilziel zum lokalen Questplan hinzugefügt.');}catch(e){toast(e.message);}};
 $('export').onclick=()=>download('MythicWalker_Questplan.json',JSON.stringify(plan,null,2),'application/json');
 $('import').onclick=()=>$('file').click();$('file').onchange=async()=>{try{const file=$('file').files[0];if(!file)return;if(file.size>2000000)throw Error('Datei zu groß (max. 2 MB).');const value=validateQuestPlan(JSON.parse(await file.text()));plan=value;save();$('view').value='plan';draw();toast('Questplan importiert.');}catch(e){toast(e.message);}finally{$('file').value='';}};
 $('edit').onclick=()=>{$('editor').value=JSON.stringify(plan,null,2);$('editor-panel').hidden=!$('editor-panel').hidden;};
 $('save-plan').onclick=()=>{try{plan=validateQuestPlan(JSON.parse($('editor').value));save();$('editor-panel').hidden=true;$('view').value='plan';draw();toast('Questplan gespeichert.');}catch(e){toast(e.message);}};
 $('overlay').onclick=()=>{
  popup=window.open('about:blank','mythic-quest-overlay','width=430,height=310');if(!popup){toast('Popup blockiert. Popups für diese Website erlauben.');return;}
  const doc=popup.document;doc.title='Mythic Walker · Quest-Overlay';doc.documentElement.lang='de';doc.body.className='quest-popup';doc.body.innerHTML='<article class="quest-current" id="quest-popup-content"></article><p class="small">Live-Verbindung über dein Dashboard. Dieses geöffnet lassen.</p>';
  const css=doc.createElement('link');css.rel='stylesheet';css.href=new URL('style.css',location.href).href;doc.head.appendChild(css);popup.focus();drawOverlay();render();
 };
 const autoDefaults={scope:'selected',stop_unknown:true,max_minutes:15,combat:false,dialogue:true};let autoPlan={...autoDefaults};
 try{const p=JSON.parse(localStorage.getItem('mythic-autoquest-plan-v1'));if(p&&['selected','group'].includes(p.scope)&&typeof p.stop_unknown==='boolean'&&typeof p.combat==='boolean'&&typeof p.dialogue==='boolean'&&Number.isInteger(p.max_minutes)&&p.max_minutes>=1&&p.max_minutes<=60)autoPlan=p;}catch{}
 for(const [k,v] of Object.entries(autoPlan))$('auto-'+k)[typeof v==='boolean'?'checked':'value']=v;
 $('auto-save').onclick=()=>{const n=Number($('auto-max_minutes').value);if(!Number.isInteger(n)||n<1||n>60){toast('Zeitlimit: 1–60 Minuten.');return;}autoPlan={scope:$('auto-scope').value,stop_unknown:$('auto-stop_unknown').checked,max_minutes:n,combat:$('auto-combat').checked,dialogue:$('auto-dialogue').checked};try{localStorage.setItem('mythic-autoquest-plan-v1',JSON.stringify(autoPlan));toast('Auto-Quest-Plan gespeichert. Es wird keine Automatik gestartet.');}catch{toast('Browser-Speicher nicht verfügbar.');}};
 draw();
 return {render,navigate(page){active=page==='quests';if(!watching()){clearTimeout(timer);timer=null;}else render();},closed(){picker.closed();clientId='';reset();message='Bridge getrennt. Live-Tracking beendet.';draw();}};
}
if(typeof module!=='undefined')module.exports={validateQuestPlan,questMatch,createQuests};
