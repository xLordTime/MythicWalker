'use strict';
function createRaids({state,command,toast,log}){
 const $=id=>document.getElementById(id),esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let raid='ds',current={running:false,phase:'Bereit',restored:true,wisps:[]},busy=false;
 const accounts=createAccountPicker({prefix:'raid',state,command,toast,beforeChange:async()=>{if(current.running){current=await command('raid_stop');state.raidRunning=false;log('Raid-Aktion vor dem Accountwechsel gestoppt.');}$('raid-wisps').innerHTML='';render();}});
 $('raid-tabs').innerHTML=MW_RAIDS.map(r=>`<button class="button compact" role="tab" data-raid="${r.id}">${esc(r.name)}</button>`).join('');
 $('raid-tabs').onclick=event=>{const button=event.target.closest('[data-raid]');if(!button)return;raid=button.dataset.raid;$('raid-wisps').innerHTML='';draw();render();};
 function draw(){
  const entry=MW_RAIDS.find(r=>r.id===raid);$('raid-title').textContent=entry.name;
  document.querySelectorAll('[data-raid]').forEach(b=>{b.classList.toggle('primary',b.dataset.raid===raid);b.setAttribute('aria-selected',String(b.dataset.raid===raid));});
  const q=$('raid-search').value.trim().toLowerCase();
  const actions=entry.actions.filter(a=>(a.label+' '+a.group).toLowerCase().includes(q));
  $('raid-actions').innerHTML=[...new Set(actions.map(a=>a.group))].map(group=>`<article class="panel raid-group"><h3>${esc(group)}</h3><div class="raid-action-grid">${actions.filter(a=>a.group===group).map(a=>`<button class="button" data-raid-action="${a.id}">${esc(a.label)}</button>`).join('')}</div></article>`).join('')||'<p>Keine passende Funktion gefunden.</p>';
 }
 function render(){
  accounts.render();
  const live=state.connected&&!state.demo&&!state.bridgeDemo,c=state.clients.find(c=>accounts.ids().includes(c.id));
  const blocked=!live||!state.raidAvailable||!c?.hooked||current.running||state.running||state.fishingRunning||busy||accounts.busy||Object.values(state.automations).some(Boolean);
  document.querySelectorAll('[data-raid-action],[data-wisp]').forEach(b=>b.disabled=blocked);
  $('raid-stop').disabled=!live||!current.running||busy;
  $('raid-status').textContent=current.running?'Aktiv':current.error?'Fehler':!live?'Live-Bridge erforderlich':!state.raidAvailable?'Bridge aktualisieren (Beta 13+)':'Bereit';
  const active=state.clients.find(c=>c.id===current.client);
  $('raid-phase').textContent=(current.running?`${active?.title||'Client '+current.client} · `:'')+(current.phase||'Bereit');
  $('raid-restore').textContent=current.restored?'Keine Raid-Angelpatches aktiv':'Raid-Angelpatches aktiv · werden beim Stoppen wiederhergestellt';
  $('raid-error').hidden=!current.error;$('raid-error').textContent=current.error||'';
 }
 async function perform(action,target){
  busy=true;render();try{current=await command('raid_start',{ids:accounts.ids(),raid,action,...(target?{target}:{})});state.raidRunning=!!current.running;log('Raid: '+action);}
  catch(e){toast(e.message);log(e.message,'error');}finally{busy=false;render();}
 }
 $('raid-actions').onclick=event=>{const b=event.target.closest('[data-raid-action]');if(b&&!b.disabled)return perform(b.dataset.raidAction);};
 $('raid-wisps').onclick=event=>{const b=event.target.closest('[data-wisp]');if(b&&!b.disabled)return perform('wisp_target',b.dataset.wisp);};
 $('raid-stop').onclick=async()=>{busy=true;render();try{current=await command('raid_stop');state.raidRunning=false;}catch(e){toast(e.message);}finally{busy=false;render();}};
 $('raid-search').oninput=()=>{draw();render();};
 draw();
 return {render,update(value){if(!value)return;current={...value};state.raidRunning=!!current.running;if(current.running)accounts.adopt(current.client);$('raid-wisps').innerHTML=current.raid===raid&&current.client===accounts.ids()[0]?(current.wisps||[]).map(w=>`<button class="button compact" data-wisp="${esc(w.id)}">${esc(w.label)} · ${Number(w.x).toFixed(0)}, ${Number(w.y).toFixed(0)}, ${Number(w.z).toFixed(0)}</button>`).join(''):'';},closed(){current={running:false,restored:true,phase:'Verbindung getrennt · Bridge-Log prüfen'};state.raidRunning=false;accounts.closed();$('raid-wisps').innerHTML='';}};
}
