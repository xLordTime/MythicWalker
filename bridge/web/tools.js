'use strict';
function createMythicTools(api){const $=id=>document.getElementById(id);
document.querySelectorAll('[data-movement]').forEach(b=>b.onclick=()=>api.action('movement',{action:b.dataset.movement,source:$('movement-leader').value||null}));$('movement-leader').onchange=()=>api.context();
const safe=fn=>async()=>{try{await fn();}catch(e){api.toast(e.message);api.log(e.message,'error');}};
$('quest-read').onclick=safe(async()=>{const rows=await api.action('quest_position',{ids:api.ids()});if(rows){$('quest-output').textContent=rows.map(r=>`${r.id} · ${r.zone} · XYZ(${r.position.map(n=>n.toFixed(1)).join(', ')})`).join('\n');}});
$('quest-go').onclick=safe(()=>api.action('quest_tp',{ids:api.ids()}));
$('nearest-go').onclick=safe(()=>{const query=$('nearest-query').value.trim();if(!query)throw Error('Entity-Name oder Suchbegriff eingeben.');return api.action('nearest_entity',{ids:api.ids(),query});});
$('speed-go').onclick=safe(()=>{const percent=Number($('speed-percent').value);if(!Number.isInteger(percent)||percent<0||percent>300)throw Error('Geschwindigkeit: ganze Zahl von 0 bis 300 %.');return api.action('speed',{ids:api.ids(),percent});});
$('speed-reset').onclick=safe(()=>api.action('restore_speed',{ids:api.ids()}));
$('camera-go').onclick=safe(()=>api.action('camera_tp',{ids:api.ids()}));
$('client-rename').onclick=safe(()=>{const title=$('client-title-input').value.trim();if(!title||title.length>80)throw Error('Fenstertitel: 1–80 Zeichen.');return api.action('rename',{ids:api.ids(),title});});
$('dialogue-toggle').onclick=safe(()=>api.action('dialogue',{ids:api.ids(),enabled:!api.dialogue()}));
$('tools-stop').onclick=safe(()=>api.action('stop',{}));
$('stats-read').onclick=safe(async()=>{const rows=await api.action('stats',{ids:api.ids()});if(!rows)return;$('stats-output').textContent=JSON.stringify(rows,null,2);});
$('import-script').onclick=()=>$('script-file').click();$('script-file').onchange=safe(async()=>{try{const file=$('script-file').files[0];if(!file)return;if(file.size>65536)throw Error('Skript zu groß (max. 64 KB).');const source=await file.text();api.importScript(source,file.name.replace(/\.txt$/i,''));}finally{$('script-file').value='';}});
return {render(){document.querySelectorAll('[data-movement]').forEach(b=>b.disabled=!api.available()||api.busy()||!api.clients().some(c=>c.hooked));const leader=$('movement-leader').value;$('movement-leader').innerHTML='<option value="">Automatisch · erster gewählter/gehookter Client</option>'+api.clients().filter(c=>c.hooked).map(c=>`<option value="${api.esc(c.id)}">${api.esc(c.title)} · ${api.esc(c.id)}</option>`).join('');$('movement-leader').value=api.clients().some(c=>c.hooked&&c.id===leader)?leader:'';const modes=api.automations();for(const mode of ['combat','dialogue','questing','sigil'])$('movement-status-'+mode+'_toggle').textContent=modes[mode]?'Läuft · erneut drücken zum Stoppen':'Inaktiv'; $('dialogue-toggle').textContent=api.dialogue()?'Dialog-Automatik stoppen':'Dialog-Automatik starten';$('tools-state').textContent=api.dialogue()?'Dialog-Automatik läuft · maximal 15 Minuten':'Aktionen für ausgewählte, gehookte Clients';}};
}
