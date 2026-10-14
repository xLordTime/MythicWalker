const assert=require('node:assert/strict'),fs=require('node:fs');
const {createLauncher}=require('../dist/launcher.js');
const html=fs.readFileSync('dist/index.html','utf8');
assert.equal([...html.matchAll(/class="nav[^\"]*" data-page="([^\"]+)"/g)][0][1],'launcher');
assert.match(html,/sandbox="allow-scripts allow-same-origin allow-forms allow-modals"/);
const code=fs.readFileSync('bridge/launcher_web/launcher.js','utf8');
assert(!/localStorage|sessionStorage|postMessage\(/.test(code));
assert.match(code,/fetch\('\/api\/'/);assert(!/fetch\(['"]https?:/.test(code));
const els=new Map();global.document={getElementById:id=>{if(!els.has(id))els.set(id,{});return els.get(id);}};
const state={connected:true,launcherAvailable:true};let messages=[],url='https://localhost:18762/#ticket='+'A'.repeat(43),nav;
const launcher=createLauncher({state,command:async()=>({url}),toast:m=>messages.push(m),navigate:p=>nav=p});
(async()=>{
 launcher.render();assert.equal(els.get('launcher-connect').disabled,false);
 await els.get('launcher-connect').onclick();assert.equal(els.get('launcher-frame').src,url);assert.equal(els.get('launcher-frame').hidden,false);
 url='https://attacker.invalid/#ticket='+'A'.repeat(43);await els.get('launcher-connect').onclick();assert.match(messages.at(-1),/Ungültige/);
 state.connected=false;launcher.render();assert.equal(els.get('launcher-frame').src,'about:blank');assert.equal(els.get('launcher-frame').hidden,true);
 els.get('launcher-clients').onclick();assert.equal(nav,'hooking');
 console.log('Launcher first tab, local-only URL, disconnect cleanup and private bundle checks passed.');
})().catch(e=>{console.error(e);process.exit(1);});
