'use strict';
function createLauncher({state,command,toast,navigate}){
 const $=id=>document.getElementById(id);let mounted=false;
 const ready=()=>state.connected&&!state.demo&&!state.bridgeDemo&&state.launcherAvailable;
 const open=async separate=>{
  if(!ready()){toast(state.connected?'Bridge mit Launcher-Unterstützung aktualisieren.':'Zuerst die lokale Bridge verbinden.');return;}
  // Reserve the window during the user's click, before waiting for the bridge.
  const popup=separate?window.open('about:blank','mythic-local-launcher'):null;
  if(popup)popup.opener=null;
  try{
   const result=await command('launcher_ticket');const url=new URL(result.url);
   if(url.origin!=='https://localhost:18762'||url.pathname!=='/'||!/^#ticket=[A-Za-z0-9_-]{40,100}$/.test(url.hash))throw Error('Ungültige lokale Launcher-Adresse.');
   if(separate){if(!popup)throw Error('Popup blockiert. Im Bridge-Widget „Launcher lokal öffnen“ wählen.');popup.location.href=url.href;}
   else{$('launcher-frame').src=url.href;$('launcher-frame').hidden=false;mounted=true;}
   $('launcher-status').textContent='Lokale Ansicht angefordert. Dort den Windows-Kontotresor entsperren. Bei leerer Ansicht „Eigenes Fenster“ verwenden.';
  }catch(e){if(popup)popup.close();toast(e.message);}
 };
 $('launcher-connect').onclick=()=>open(false);$('launcher-window').onclick=()=>open(true);$('launcher-clients').onclick=()=>navigate('hooking');
 return{render(){const ok=ready();$('launcher-connect').disabled=!ok;$('launcher-window').disabled=!ok;
  if(!ok){if(mounted){$('launcher-frame').src='about:blank';$('launcher-frame').hidden=true;mounted=false;}$('launcher-status').textContent=state.demo||state.bridgeDemo?'Launcher benötigt die lokale Windows-Live-Bridge.':state.connected?'Bridge aktualisieren: Launcher ab Beta 15 verfügbar.':'Verbinde deine Bridge, um den lokalen Launcher zu öffnen.';}
  else if(!mounted)$('launcher-status').textContent='Bridge bereit. Launcher verbinden oder in einem eigenen lokalen Fenster öffnen.';
 }};
}
if(typeof module!=='undefined')module.exports={createLauncher};
