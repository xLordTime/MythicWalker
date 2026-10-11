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
const local=new Map();const context={document,console,localStorage:{getItem:k=>local.get(k)||null,setItem:(k,v)=>local.set(k,v)},location:{hash:''},history:{replaceState(){}},window:{addEventListener(){},scrollTo(){}},setTimeout,clearTimeout,AbortController,crypto:require('node:crypto').webcrypto,Blob,URL,URLSearchParams,fetch:async()=>({json:async()=>({sources:[]})})};
const launchToken='test_pair_token_abcdefghijklmnopqrstuvwxyz';
if(process.env.TEST_PAIR==='1'){
 context.location={hash:'#pair='+launchToken,pathname:'/',search:''};context.history.replaceState=(state,title,url)=>{context.location.hash=url.slice(url.indexOf('#'));};
 class Socket{
  constructor(url){this.url=url;this.readyState=1;Socket.instance=this;setTimeout(()=>this.onopen(),0);}
  send(text){const data=JSON.parse(text);if(data.type==='auth'){this.auth=data;setTimeout(()=>this.onmessage({data:JSON.stringify({type:'ready',version:'0.3.0',backend:'demo',demo:true})}),0);}else{let result={updated:true};if(data.op==='set_settings')result={settings:data.args.settings,hotkeys:{supported:false,active:[],errors:{}}};setTimeout(()=>this.onmessage({data:JSON.stringify({type:'result',id:data.id,ok:true,data:result})}),0);}}
 }
 context.WebSocket=Socket;
}
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/settings.js','utf8'),context);vm.runInContext(fs.readFileSync('dist/tools.js','utf8'),context);vm.runInContext(fs.readFileSync('dist/app.js','utf8'),context);
function el(id){return elements.get(id);}
(async()=>{
 if(process.env.TEST_PAIR==='1'){
  await new Promise(r=>setTimeout(r,30));assert.equal(context.location.hash,'#overview');assert.equal(context.WebSocket.instance.auth.token,launchToken);assert.equal(context.WebSocket.instance.url,'wss://localhost:18761/ws');assert.equal(el('bridge-token').value,'');assert(!el('log-list').innerHTML.includes(launchToken));console.log('Browser auto-pairing, fragment cleanup and token redaction passed.');process.exit(0);
 }
 await el('settings-button').click();assert.equal(el('breadcrumb').textContent,'Einstellungen');
 el('setting-key_seconds').value='0.6';el('setting-accent').value='teal';await el('save-settings').click();assert.equal(document.body.dataset.accent,'teal');assert.equal(el('key-seconds').value,.6);
 el('demo-button').click();assert.equal(el('metric-clients').textContent,3);
 async function shortcut(key){await listeners.keydown({key,ctrlKey:true,altKey:true,shiftKey:false,metaKey:false,repeat:false,target:new Element('target'),preventDefault(){},stopImmediatePropagation(){}});await new Promise(r=>setTimeout(r,5));}
 await shortcut('H');assert.equal(el('metric-hooks').textContent,1);
 await el('quest-read').click();assert.match(el('quest-output').textContent,/500/);await el('quest-go').click();await el('stats-read').click();assert.match(el('stats-output').textContent,/current_gold/);await el('dialogue-toggle').click();assert.match(el('tools-state').textContent,/läuft/);await el('tools-stop').click();
 await shortcut('U');assert.equal(el('metric-hooks').textContent,0);
 // Persist the saved configuration after exercising shortcuts.
 await el('save-settings').click();
 assert.equal(JSON.parse(local.get('mythic-settings-v3')).key_seconds,.6);
 console.log('App initialization, settings save, demo hook and unhook shortcuts passed.');
 clearTimeout();process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
