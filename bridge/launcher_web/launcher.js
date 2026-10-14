'use strict';
// This bundle is shipped only inside the Bridge, never loaded from the hosted Site.
// No browser storage, outbound requests, telemetry, or postMessage of account data.
(()=>{
 const $=id=>document.getElementById(id),selected=new Set();let session=null,snapshot=null,editing=false,busy=false,pendingDelete=null;
 const ticket=new URLSearchParams(location.hash.slice(1)).get('ticket');history.replaceState(null,'',location.pathname);
 function notice(text){$('notice').textContent=text;}
 async function api(action,args={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),25000);
  try{
   const response=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json',...(session?{Authorization:'Bearer '+session}:{})},body:JSON.stringify(args),cache:'no-store',credentials:'omit',signal:controller.signal});
   if(response.status===401){session=null;scrub();throw Error('Sitzung abgelaufen. Im Launcher-Tab erneut verbinden.');}
   if(!response.ok){let message='Lokaler Vorgang fehlgeschlagen.';try{message=(await response.json()).error||message;}catch{}throw Error(message);}
   return await response.json();
  }finally{clearTimeout(timer);}
 }
 function scrub(){pendingDelete=null;$('delete-dialog').close();snapshot=null;selected.clear();$('workspace').hidden=true;$('locked').hidden=false;$('accounts').replaceChildren();$('account-form').reset();$('account-form').hidden=true;$('master-password').value='';editing=false;$('unlock').disabled=!session;}
 function regionOptions(el,regions){el.replaceChildren();for(const [key,name] of Object.entries(regions)){const opt=document.createElement('option');opt.value=key;opt.textContent=key.toUpperCase()+' · '+name;el.append(opt);}}
 function pathsFromForm(){const paths={};for(const r of Object.keys(snapshot.regions))paths[r]=$('path-'+r).value;return paths;}
 function render(data,refreshForms=false){
  snapshot=data;$('locked').hidden=data.unlocked;$('workspace').hidden=!data.unlocked;
  if(!data.unlocked){scrub();return;}
  const present=new Set(data.accounts.map(a=>a.id));for(const id of selected)if(!present.has(id))selected.delete(id);
  $('accounts').replaceChildren();
  if(!data.accounts.length){const p=document.createElement('p');p.className='muted';p.textContent='Noch keine Accounts. Füge einen hinzu oder übernimm dein Wiz-Q-Profil.';$('accounts').append(p);}
  for(const a of data.accounts){
   const row=document.createElement('div');row.className='account';const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.checked=selected.has(a.id);box.disabled=data.progress.running;box.onchange=()=>{box.checked?selected.add(a.id):selected.delete(a.id);updateButtons();};label.append(box,document.createTextNode(a.name));const small=document.createElement('small');small.textContent=a.region.toUpperCase()+' · '+a.username;label.append(small);row.append(label);
   for(const [text,fn] of [['Bearbeiten',()=>edit(a)],['Löschen',async()=>{pendingDelete=a.id;$('delete-dialog').showModal();}]]){const b=document.createElement('button');b.textContent=text;b.className='secondary';b.disabled=data.progress.running;b.onclick=guard(fn);row.append(b);}
   $('accounts').append(row);
  }
  $('progress').textContent=data.progress.message+' ('+data.progress.done+'/'+data.progress.total+')';$('processes').textContent=data.processes.length?'Gestartete Prozesse: '+data.processes.join(', '):'Keine vom Launcher gestarteten Prozesse aktiv.';
  $('folder').textContent='Lokales Profil: '+data.folder;$('legacy-info').textContent=data.legacy?(data.imported?'Wiz-Q-Profil erkannt. Ein erneuter Import ergänzt neue Konten.':'Vorhandenes Wiz-Q-Profil erkannt.'):'Noch keine bestehende Wiz-Q-Kontodatei gefunden.';$('import').disabled=!data.legacy||data.progress.running;
  if(refreshForms){
   regionOptions($('quick-region'),data.regions);regionOptions($('account-region'),data.regions);$('region-paths').replaceChildren();
   for(const [key,name] of Object.entries(data.regions)){const label=document.createElement('label');label.textContent=key.toUpperCase()+' · '+name;const input=document.createElement('input');input.id='path-'+key;input.value=data.settings.paths[key]||'';input.placeholder='Installationsordner';input.maxLength=1000;label.append(input);$('region-paths').append(label);}
   $('login-wait').value=data.settings.login_wait;
  }
  updateButtons();
 }
 function updateButtons(){if(!snapshot)return;$('launch-selected').disabled=!selected.size||snapshot.progress.running;$('quick-start').disabled=snapshot.progress.running;$('stop').disabled=!snapshot.progress.running;$('select-all').checked=!!snapshot.accounts.length&&selected.size===snapshot.accounts.length;}
 function guard(fn){return async event=>{event?.preventDefault();if(busy)return;busy=true;try{await fn(event);}catch(e){notice(e.name==='AbortError'?'Zeitlimit erreicht. Status prüfen, Start nicht blind wiederholen.':e.message);}finally{busy=false;}};}
 function edit(a){editing=true;$('account-form').hidden=false;$('account-form').reset();$('account-id').value=a?.id||'';$('account-name').value=a?.name||'';$('account-user').value=a?.username||'';$('account-region').value=a?.region||'de';$('edit-title').textContent=a?'Account bearbeiten':'Account hinzufügen';$('account-password').required=!a;$('account-name').focus();}
 $('delete-cancel').onclick=()=>{pendingDelete=null;$('delete-dialog').close();};
 $('delete-confirm').onclick=guard(async()=>{if(!pendingDelete)return;const id=pendingDelete;pendingDelete=null;$('delete-dialog').close();render(await api('delete',{id}));notice('Konto lokal gelöscht.');});
 $('unlock').onclick=guard(async()=>{render(await api('unlock'),true);notice('Tresor lokal geöffnet. Kontodaten sind nur in dieser lokalen Ansicht sichtbar.');});
 $('lock').onclick=guard(async()=>{await api('lock');scrub();notice('Tresor gesperrt. Bereits gestartete Spiele bleiben offen.');});
 $('new-account').onclick=()=>edit(null);$('cancel-edit').onclick=()=>{$('account-form').reset();$('account-form').hidden=true;editing=false;};
 $('account-form').onsubmit=guard(async()=>{const args={id:$('account-id').value||null,name:$('account-name').value,username:$('account-user').value,password:$('account-password').value,region:$('account-region').value};$('account-password').value='';try{render(await api('save',args));$('account-form').reset();$('account-form').hidden=true;editing=false;notice('Account lokal verschlüsselt gespeichert.');}finally{args.password='';}});
 $('select-all').onchange=()=>{if($('select-all').checked)snapshot.accounts.forEach(a=>selected.add(a.id));else selected.clear();render(snapshot);};
 $('launch-selected').onclick=guard(async()=>{await api('launch',{ids:[...selected]});render(await api('state'));});
 $('quick-start').onclick=guard(async()=>{await api('launch',{region:$('quick-region').value,count:Number($('quick-count').value)});render(await api('state'));});
 $('stop').onclick=guard(async()=>render(await api('stop')));
 $('save-settings').onclick=guard(async()=>{render(await api('settings',{paths:pathsFromForm(),login_wait:Number($('login-wait').value)}));notice('Installationen lokal gespeichert.');});
 $('detect').onclick=guard(async()=>{const data=await api('detect');for(const [r,path] of Object.entries(data.paths))$('path-'+r).value=path;notice(Object.keys(data.paths).length?'Installationen gefunden. Mit „Installationen lokal speichern“ übernehmen.':'Keine Installation gefunden. Pfad manuell eintragen.');});
 $('import').onclick=guard(async()=>{let password=$('master-password').value;$('master-password').value='';try{const result=await api('import',{password});render(await api('state'));notice(result.added+' Accounts lokal übernommen. Originaldatei unverändert.');}finally{password='';}});
 document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{for(const tab of ['accounts','regions','import'])$('tab-'+tab).hidden=tab!==b.dataset.tab;document.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));});
 if(ticket)guard(async()=>{session=(await api('exchange',{ticket})).session;$('unlock').disabled=false;notice('Lokale Verbindung hergestellt. Öffne deinen Windows-Kontotresor.');})();else notice('Diesen Launcher über den Launcher-Tab oder das Bridge-Widget öffnen.');
 setInterval(async()=>{if(!session||busy||editing)return;try{const data=await api('state');render(data);}catch(e){notice(e.message);}},3000);
 window.addEventListener('pagehide',()=>{if(session)fetch('/api/end',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+session},body:'{}',credentials:'omit',keepalive:true}).catch(()=>{});session=null;scrub();});
})();
