'use strict';
function createFishing({state,command,toast,log}){
 const $=id=>document.getElementById(id);
 let current={running:false,catches:0,phase:'Bereit zum Angeln',restored:true},busy=false;
 const accounts=createAccountPicker({prefix:'fish',state,command,toast,beforeChange:async()=>{if(current.running){current=await command('fishing_stop');state.fishingRunning=false;log('Angeln vor dem Accountwechsel gestoppt; Originalbytes wiederhergestellt.');}render();}});
 const ids=()=>accounts.ids();
 const defaults={'fish-chests':'fish','fish-school':'Any','fish-rank':2,'fish-id':0,'fish-min':0,'fish-max':999,'fish-limit':0,'fish-minutes':0,'fish-popup':true,'fish-speed-enabled':false,'fish-speed':1,'fish-require-all':true,'fish-poll':.005,'fish-after-click':.01,'fish-retry':.01,'fish-window':.02,'fish-game-state':.05};
 const fields=Object.keys(defaults),checkboxes=fields.filter(id=>typeof defaults[id]==='boolean');
 function fill(values){for(const id of fields){if(checkboxes.includes(id))$(id).checked=values[id]===true;else $(id).value=String(values[id]??defaults[id]);}}
 fill(defaults);
 try{const saved=JSON.parse(localStorage.getItem('mythic-fishing-v2')||'null');if(saved&&typeof saved==='object')fill({...defaults,...saved});}catch{}
 $('fish-defaults').onclick=()=>{fill(defaults);toast('Original-Einstellungen geladen.');};
 function render(){
  accounts.render();
  const selected=state.clients.filter(c=>ids().includes(c.id));
  $('fishing-selection').textContent=selected.length===1?`${selected[0].title} · PID ${selected[0].pid} · ${selected[0].hooked?'Hook aktiv':'Zuerst hooken'}`:'Seitlich einen Angel-Account auswählen.';
  const live=state.connected&&!state.demo&&!state.bridgeDemo;
  $('fish-start').disabled=!live||selected.length!==1||!selected[0]?.hooked||current.running||state.running||state.raidRunning||busy||accounts.busy||Object.values(state.automations).some(Boolean);
  $('fish-stop').disabled=!live||!current.running||busy;
  fields.forEach(id=>$(id).disabled=current.running||busy);$('fish-defaults').disabled=current.running||busy;
  $('fishing-status').textContent=current.stopping?'Stoppt …':current.running?'Angelt':!live?'Live-Bridge erforderlich':current.error?'Fehler':'Bereit';
  $('fish-count').textContent=String(current.catches||0);$('fish-phase').textContent=(current.phase||'Bereit')+(current.running&&current.idle_seconds>=10?` · ${current.idle_seconds} s`:'');$('fish-activity').textContent=current.last_activity||'';
  $('fish-restore').textContent=current.client_closed?'Spielprozess beendet · kein Wiederherstellen in einem geschlossenen Prozess':current.restored?'Keine Angel-Patches aktiv · Originalcode bestätigt':'Angel-Patches aktiv · Stoppen stellt Originalcode wieder her';
  $('fish-error').hidden=!current.error;$('fish-error').textContent=current.error||'';
 }
 async function perform(op,args={}){busy=true;render();try{current=await command(op,args);state.fishingRunning=!!current.running;log(op==='fishing_start'?'Fisch-Bot gestartet.':'Fisch-Bot gestoppt; Aufräumstatus prüfen.');}catch(e){toast(e.message);log(e.message,'error');}finally{busy=false;render();}}
 $('fish-start').onclick=()=>{const settings={chests:$('fish-chests').value==='chests',school:$('fish-school').value,rank:Number($('fish-rank').value),fish_id:Number($('fish-id').value),size_min:Number($('fish-min').value),size_max:Number($('fish-max').value),max_catches:Number($('fish-limit').value),minutes:Number($('fish-minutes').value),skip_popup:$('fish-popup').checked,speed_enabled:$('fish-speed-enabled').checked,speed:Number($('fish-speed').value),require_all_patches:$('fish-require-all').checked,poll_interval:Number($('fish-poll').value),after_click:Number($('fish-after-click').value),retry_delay:Number($('fish-retry').value),window_wait:Number($('fish-window').value),game_state_wait:Number($('fish-game-state').value)};try{localStorage.setItem('mythic-fishing-v2',JSON.stringify(Object.fromEntries(fields.map(id=>[id,checkboxes.includes(id)?$(id).checked:$(id).value]))));}catch{}return perform('fishing_start',{ids:ids(),settings});};
 $('fish-stop').onclick=()=>perform('fishing_stop');
 return {render,update(value){if(value&&typeof value==='object'){current={...value};state.fishingRunning=!!current.running;if(current.running)accounts.adopt(current.client);}},closed(){accounts.closed();state.fishingRunning=false;current={...current,running:false,phase:'Verbindung getrennt · Aufräumen im Bridge-Log prüfen'};}};
}
