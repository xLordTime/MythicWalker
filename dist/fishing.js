'use strict';
function createFishing({state,ids,command,toast,log}){
 const $=id=>document.getElementById(id);
 let current={running:false,catches:0,phase:'Bereit zum Angeln',restored:true},busy=false;
 const fields=['fish-chests','fish-school','fish-rank','fish-id','fish-min','fish-max','fish-limit','fish-minutes','fish-distance'];
 try{const saved=JSON.parse(localStorage.getItem('mythic-fishing-v1')||'null');if(saved&&typeof saved==='object')for(const id of fields){if(id==='fish-distance')$(id).checked=saved[id]===true;else if(saved[id]!=null)$(id).value=String(saved[id]);}}catch{}
 function render(){
  const selected=state.clients.filter(c=>ids().includes(c.id));
  $('fishing-selection').textContent=selected.length===1?`${selected[0].title} · PID ${selected[0].pid} · ${selected[0].hooked?'Hook aktiv':'Zuerst hooken'}`:'Genau einen Client unter Hooking auswählen.';
  const live=state.connected&&!state.demo&&!state.bridgeDemo;
  $('fish-start').disabled=!live||selected.length!==1||!selected[0]?.hooked||current.running||state.running||busy||Object.values(state.automations).some(Boolean);
  $('fish-stop').disabled=!live||!current.running||busy;
  fields.forEach(id=>$(id).disabled=current.running||busy);
  $('fishing-status').textContent=current.running?'Angelt':!live?'Live-Bridge erforderlich':current.error?'Fehler':'Bereit';
  $('fish-count').textContent=String(current.catches||0);$('fish-phase').textContent=current.phase||'Bereit';
  $('fish-restore').textContent=current.restored?'Keine Angel-Patches aktiv · Originalcode bestätigt':'Angel-Patches aktiv · Stoppen stellt Originalcode wieder her';
  $('fish-error').hidden=!current.error;$('fish-error').textContent=current.error||'';
 }
 async function perform(op,args={}){busy=true;render();try{current=await command(op,args);log(op==='fishing_start'?'Fisch-Bot gestartet.':'Fisch-Bot gestoppt; Aufräumstatus prüfen.');}catch(e){toast(e.message);log(e.message,'error');}finally{busy=false;render();}}
 $('fish-start').onclick=()=>{const settings={chests:$('fish-chests').value==='chests',school:$('fish-school').value,rank:Number($('fish-rank').value),fish_id:Number($('fish-id').value),size_min:Number($('fish-min').value),size_max:Number($('fish-max').value),max_catches:Number($('fish-limit').value),minutes:Number($('fish-minutes').value),distance_patch:$('fish-distance').checked};try{localStorage.setItem('mythic-fishing-v1',JSON.stringify(Object.fromEntries(fields.map(id=>[id,id==='fish-distance'?$(id).checked:$(id).value]))));}catch{}return perform('fishing_start',{ids:ids(),settings});};
 $('fish-stop').onclick=()=>perform('fishing_stop');
 return {render,update(value){if(value&&typeof value==='object')current={...value};},closed(){current={...current,running:false,phase:'Verbindung getrennt · Aufräumen im Bridge-Log prüfen'};}};
}
