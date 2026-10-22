// Exercise the real app initialization and shortcuts using a minimal DOM host.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('dist/index.html','utf8'),elements=new Map(),listeners={};
class Element {
 constructor(id,tag='div'){this.id=id;this.tagName=tag;this.value='';this.checked=false;this.disabled=false;this.hidden=false;this.textContent='';this.innerHTML='';this.style={};this.dataset={};this.classList={toggle(){}};this.events={};}
 addEventListener(type,fn){this.events[type]=fn;}
 set innerHTML(value){this._html=value;for(const m of value.matchAll(/<input[^>]*id="([^"]+)"[^>]*value="([^"]*)"/g)){const e=new Element(m[1],'input');e.value=m[2];elements.set(e.id,e);}}
 get innerHTML(){return this._html;}
 querySelectorAll(){return [];}
 insertAdjacentHTML(){} removeAttribute(){} focus(){} closest(){return null;} click(){if(!this.disabled&&this.onclick)return this.onclick();}
}
for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)){const el=new Element(m[2],m[1]);const value=m[0].match(/\bvalue="([^"]*)"/);if(value)el.value=value[1];elements.set(el.id,el);}
const nav=[...html.matchAll(/class="nav[^"]*" data-page="([^"]+)"/g)].map(m=>{const e=new Element('nav-'+m[1],'button');e.dataset.page=m[1];return e;});
const document={body:new Element('body'),getElementById:id=>{if(!elements.has(id)){if(id.startsWith('binding-'))elements.set(id,new Element(id,'input'));else throw Error('Missing '+id);}return elements.get(id);},querySelectorAll:sel=>sel==='.nav'?nav:sel==='.page'?[...elements.values()].filter(e=>e.id.startsWith('page-')):[],querySelector:()=>null,addEventListener:(type,fn)=>listeners[type]=fn,createElement:()=>new Element('new')};
const local=new Map();const context={document,console,sessionStorage:{getItem:k=>local.get(k)||null,setItem:(k,v)=>local.set(k,v),removeItem:k=>local.delete(k)},localStorage:{getItem:k=>local.get(k)||null,setItem:(k,v)=>local.set(k,v)},location:{hash:''},history:{replaceState(){}},window:{addEventListener(){},scrollTo(){}},setTimeout,clearTimeout,AbortController,crypto:require('node:crypto').webcrypto,Blob,URL,URLSearchParams,fetch:async url=>({json:async()=>url==='upstream-bots.json'?JSON.parse(fs.readFileSync('dist/upstream-bots.json','utf8')):{sources:[]}})};
const launchToken='test_pair_token_abcdefghijklmnopqrstuvwxyz';
if(process.env.TEST_PAIR==='1'){
 context.location={hash:'#pair='+launchToken,pathname:'/',search:''};context.history.replaceState=(state,title,url)=>{context.location.hash=url.slice(url.indexOf('#'));};
 class Socket{
  constructor(url){this.url=url;this.readyState=1;this.requests=[];Socket.instance=this;setTimeout(()=>this.onopen(),0);}
  send(text){const data=JSON.parse(text);if(data.type==='auth'){this.auth=data;const version=Number(process.env.TEST_SOUND_VERSION||0),capabilities=version?['sound_files',...(version>=18?['sound_library']:[]),...(version>=19?['sound_picker']:[])]:[];setTimeout(()=>this.onmessage({data:JSON.stringify({type:'ready',version:'0.1.1',release:'v0.1.1-beta.'+version,backend:version?'DE fixture':'demo',demo:!version,capabilities})}),0);}else{this.requests.push(data);let result={updated:true};if(data.op==='set_settings')result={settings:data.args.settings,hotkeys:{supported:false,active:[],errors:{}}};if(data.op==='sound_status')result={running:false,id:0,message:'Bereit'};if(['sound_archives','sound_config'].includes(data.op))result={installation:'C:\\Wizard101',archives:[{id:'Sound.wad',bytes:1000}]};if(data.op==='sound_changes')result={changes:[],errors:[]};if(data.op==='sound_files')result={files:[],total:0,changes:0};setTimeout(()=>this.onmessage({data:JSON.stringify({type:'result',id:data.id,ok:true,data:result})}),0);}}
 }
 context.WebSocket=Socket;
}
vm.createContext(context);
const scriptFiles=[...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*>/g)].map(m=>m[1].split('?')[0]);
assert(scriptFiles.indexOf('botlang.js')<scriptFiles.indexOf('app.js'));
assert(scriptFiles.includes('default-library.js')&&scriptFiles.includes('bot-catalog.js')&&scriptFiles.includes('diagnostics.js'));
for(const file of scriptFiles)vm.runInContext(fs.readFileSync('dist/'+file,'utf8'),context,{filename:file});
assert(context.window.mwDiagnostics.snapshot().some(e=>e.event==='app.init.ready'));

function el(id){return elements.get(id);}
async function waitFor(check,message){const deadline=Date.now()+4000;while(!check()){assert(Date.now()<deadline,message);await new Promise(r=>setTimeout(r,5));}}
(async()=>{
 if(process.env.TEST_PAIR==='1'){
  await waitFor(()=>el('pairing-result').textContent.startsWith('Verbunden'),'Pairing did not complete');assert.equal(context.location.hash,'#overview');assert.equal(context.WebSocket.instance.auth.token,launchToken);assert.equal(context.WebSocket.instance.url,'wss://localhost:18761/ws');assert.equal(el('bridge-token').value,'');assert(!el('log-list').innerHTML.includes(launchToken));assert(!JSON.stringify(context.window.mwDiagnostics.snapshot()).includes(launchToken));assert(context.window.mwDiagnostics.snapshot().some(e=>e.event==='ws.auth.sent'));
  if(process.env.TEST_SOUND_VERSION){
   const version=Number(process.env.TEST_SOUND_VERSION);await nav.find(n=>n.dataset.page==='sound').click();await waitFor(()=>!el('sound-configure').disabled&&el('sound-archive').innerHTML.includes('Sound.wad'),'Sound installation initialization did not complete');
   assert(!el('sound-path').disabled);assert(!el('sound-configure').disabled);assert(!el('sound-archive').disabled);
   assert.equal(el('sound-browse').disabled,version<19);assert.equal(el('sound-search-all').disabled,version<18);
   assert(el('sound-archive').innerHTML.includes('Sound.wad'));
   await el('sound-configure').click();assert(context.WebSocket.instance.requests.some(r=>r.op==='sound_files'));
   if(version===17)assert(!context.WebSocket.instance.requests.some(r=>r.op==='sound_changes'));
   console.log('Real app handshake and folder/archive controls passed for bridge beta '+version);
  }else console.log('Browser auto-pairing, fragment cleanup and token redaction passed.');process.exit(0);
 }
 assert.equal(el('setting-launcher_enabled').checked,false);assert.equal(nav.find(n=>n.dataset.page==='launcher').hidden,true);
 await nav.find(n=>n.dataset.page==='launcher').click();assert.equal(el('breadcrumb').textContent,'Übersicht');
 await el('settings-button').click();assert.equal(el('breadcrumb').textContent,'Einstellungen');
 el('setting-launcher_enabled').checked=true;el('setting-key_seconds').value='0.6';el('setting-accent').value='teal';await el('save-settings').click();assert.equal(document.body.dataset.accent,'teal');assert.equal(el('key-seconds').value,.6);
 assert.equal(nav.find(n=>n.dataset.page==='launcher').hidden,false);await nav.find(n=>n.dataset.page==='launcher').click();assert.equal(el('breadcrumb').textContent,'Launcher');
 el('demo-button').click();assert.equal(el('metric-clients').textContent,3);
 async function shortcut(key){await listeners.keydown({key,ctrlKey:true,altKey:true,shiftKey:false,metaKey:false,repeat:false,target:new Element('target'),preventDefault(){},stopImmediatePropagation(){}});await new Promise(r=>setTimeout(r,5));}
 await shortcut('H');assert.equal(el('metric-hooks').textContent,1);
 await el('quest-read').click();assert.match(el('quest-output').textContent,/500/);await el('quest-go').click();await el('stats-read').click();assert.match(el('stats-output').textContent,/current_gold/);await el('dialogue-toggle').click();assert.match(el('tools-state').textContent,/läuft/);await el('tools-stop').click();
 el('script-template').value='2';await el('load-template').click();assert.match(el('script-editor').value,/navquest/);await el('validate-script').click();assert.match(el('script-validation').textContent,/Syntax gültig/);
 assert.match(el('block-list').innerHTML,/call safe_mob_pull/);
 el('block-name').value='mine';el('block-description').value='Mein Block';el('block-source').value='mass sendkey X, 0.1';await el('save-block').click();assert.equal(JSON.parse(local.get('mythic-blocks-v1'))[0].name,'mine');
 el('script-editor').value='times 999999 {\ncall mine\ncall safe_mob_pull\n}';await el('validate-script').click();assert.match(el('script-validation').textContent,/Syntax gültig/);
 el('block-source').value='call missing';await el('save-block').click();assert.match(el('toast').textContent,/Unbekannter Block/);assert.equal(JSON.parse(local.get('mythic-blocks-v1'))[0].source,'mass sendkey X, 0.1');
 await new Promise(r=>setTimeout(r,0));assert.match(el('bot-catalog-status').textContent,/12 Bots/);assert.match(el('bot-catalog-status').textContent,/12 aktiv/);
 await el('combat-read').click();assert.match(el('combat-cards').innerHTML,/LifeBlade/);
 for(const [page,label] of [['quests','Questen'],['hooking','Hooking'],['combat','Combat'],['scripts','Skripte / Bot'],['tools','Tools'],['fishing','Angeln'],['raid','Raid']]){await nav.find(n=>n.dataset.page===page).click();assert.equal(el('breadcrumb').textContent,label);}
 assert.equal(el('fish-start').disabled,true,'Fishing is live-only in demo');
 await shortcut('U');assert.equal(el('metric-hooks').textContent,0);
 // Persist the saved configuration after exercising shortcuts.
 await el('save-settings').click();
 assert.equal(JSON.parse(local.get('mythic-settings-v3')).key_seconds,.6);
 console.log('App initialization, settings save, demo hook and unhook shortcuts passed.');
 clearTimeout();process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
