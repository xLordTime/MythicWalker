'use strict';
function createAccountPicker({prefix,state,command,toast,beforeChange=async()=>{}}){
 const $=suffix=>document.getElementById(prefix+'-'+suffix),esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 let selected='',busy=false,initialized=false,signature='';
 function client(){return state.clients.find(c=>String(c.id)===selected);}
 function render(){
  if(!initialized&&state.clients.length){const hooked=state.clients.filter(c=>c.hooked);if(hooked.length===1)selected=String(hooked[0].id);initialized=true;}
  const sig=JSON.stringify(state.clients.map(c=>[c.id,c.title,c.hooked]));
  if(sig!==signature){signature=sig;$('account').innerHTML='<option value="">Account auswählen …</option>'+state.clients.map(c=>`<option value="${esc(c.id)}">${esc(c.title)} · PID ${esc(c.pid)}${c.hooked?' · Hook aktiv':''}</option>`).join('');}
  $('account').value=client()?selected:'';
  const c=client(),live=state.connected&&!state.demo&&!state.bridgeDemo;
  $('account').disabled=busy||!live;
  $('account-info').textContent=c?`PID ${c.pid} · ${c.hooked?'Hook aktiv':'Nicht gehookt'}\n${c.zone||'Zone unbekannt'}`:selected?'Client nicht mehr verfügbar. Anderen Account auswählen.':'Wähle den Spielclient für diesen Tab.';
  $('account-hook').disabled=busy||!live||!c||c.hooked||state.fishingRunning||state.raidRunning;
  $('account-scan').disabled=busy||!live;
 }
 async function choose(value){
  const previous=selected;
  if(value===previous)return;
  busy=true;render();
  try{await beforeChange();selected=value;}catch(e){selected=previous;toast(e.message);}finally{busy=false;render();}
 }
 $('account').onchange=event=>choose(event.target.value);
 async function run(op,args={}){busy=true;render();try{const result=await command(op,args);if(op==='hook'&&Array.isArray(result)&&result.some(r=>!r.ok))throw Error(result.find(r=>!r.ok).error||'Hook fehlgeschlagen.');}catch(e){toast(e.message);}finally{busy=false;render();}}
 $('account-hook').onclick=()=>run('hook',{ids:ids()});
 $('account-scan').onclick=()=>run('scan');
 function ids(){const c=client();return c?[c.id]:[];}
 return {ids,render,choose,get busy(){return busy;},adopt(id){if(id!==null&&id!==undefined){selected=String(id);initialized=true;}},closed(){selected='';initialized=false;signature='';}};
}
