const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {soundPcm}=require('../dist/sounds.js');
const pcm=soundPcm({numberOfChannels:2,length:3,sampleRate:22050,getChannelData:c=>c?[-1,0,2]:[1,-2,NaN]});
const v=new DataView(pcm.buffer);
assert.equal(Buffer.from(pcm.slice(0,4)).toString(),'RIFF');assert.equal(v.getUint32(4,true),pcm.length-8);
assert.equal(v.getUint16(22,true),2);assert.equal(v.getUint32(24,true),22050);assert.equal(v.getUint16(34,true),16);
assert.deepEqual(Array.from({length:6},(_,i)=>v.getInt16(44+i*2,true)),[32767,-32768,-32768,0,0,32767]);
assert.throws(()=>soundPcm({numberOfChannels:3,length:100,sampleRate:22050}));
assert.throws(()=>soundPcm({numberOfChannels:1,length:22050*16,sampleRate:22050}));

const elements=new Map(),timers=new Map();let tid=0,buttons=[],requests=[],job={running:false,id:0,message:'Bereit.'},inspectDelay=null;
function el(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,disabled:false,textContent:'',innerHTML:'',files:[],removeAttribute(k){delete this[k];}});return elements.get(id);}
const source=fs.readFileSync('dist/assets/sounds/damage.ogg');
const row={name:'Sounds/<hurt>.ogg',format:'ogg',bytes:source.length,candidate:true,changed:false};
const original={format:'ogg',duration:3.38,rate:44100,channels:1,data:source.toString('base64'),sha256:'a'.repeat(64)};
const context={module:{exports:{}},console,URL,Blob,Uint8Array,TextDecoder,DataView,window:{},
 btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary'),
 fetch:async()=>({ok:true,arrayBuffer:async()=>source.buffer.slice(source.byteOffset,source.byteOffset+source.length)}),
 setTimeout:fn=>{timers.set(++tid,fn);return tid;},clearTimeout:id=>timers.delete(id),
 document:{getElementById:el,querySelectorAll:()=>{buttons=Array.from(el('sound-list').innerHTML.matchAll(/data-sound-row="(\d+)"/g),m=>({dataset:{soundRow:m[1]}}));return buttons;}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/sounds.js','utf8'),context);
const state={connected:false,soundAvailable:true},errors=[];
const controller=context.module.exports.createSounds({state,toast:e=>errors.push(e),esc:s=>String(s).replaceAll('<','&lt;').replaceAll('>','&gt;'),command:async(op,args)=>{
 requests.push({op,args});
 if(op==='sound_status')return job;
 if(op==='sound_archives')return{installation:'C:\\Wizard101',archives:[{id:'Sound-WorldData.wad',bytes:1000}]};
 if(op==='sound_files')return{files:[row],total:1,changes:row.changed?1:0};
 if(op==='sound_inspect')return inspectDelay?await inspectDelay:original;
 if(op==='sound_apply'){job={running:true,id:1,message:'Arbeitskopie'};return{started:true,id:1};}
 throw Error('Unexpected command '+op);
}});
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 controller.navigate('sound');assert.equal(requests.length,0);assert(el('sound-apply').disabled);
 state.connected=true;controller.render();await flush();assert.equal(requests.filter(r=>r.op==='sound_apply').length,0);
 await el('sound-load').onclick();assert(el('sound-list').innerHTML.includes('&lt;hurt&gt;'));
 await buttons[0].onclick();assert(el('sound-apply').disabled);assert(el('sound-original').src.startsWith('blob:'));
 await el('sound-preset').onclick();assert(el('sound-apply').disabled,'Explicit confirmation required');
 el('sound-confirm').checked=true;el('sound-confirm').onchange();assert(!el('sound-apply').disabled);
 await el('sound-apply').onclick();const apply=requests.find(r=>r.op==='sound_apply');
 assert.equal(apply.args.name,row.name);assert.equal(apply.args.archive,'Sound-WorldData.wad');assert.equal(apply.args.expected,original.sha256);
 assert.equal(apply.args.data,source.toString('base64'));assert(el('sound-apply').disabled,'No double writes while job running');
 row.changed=true;job={running:false,id:1,message:'Ersetzt',result:{backup:'local-backup'}};
 await el('sound-check').onclick();await buttons[0].onclick();assert(!el('sound-preset').disabled);
 await el('sound-check').onclick();assert(!el('sound-preset').disabled,'Completed poll must preserve a new selection');
 assert(el('sound-restore').disabled);el('sound-confirm').checked=true;el('sound-confirm').onchange();assert(!el('sound-restore').disabled);
 let resolve;inspectDelay=new Promise(r=>resolve=r);const pending=buttons[0].onclick();await flush();
 state.connected=false;controller.closed();resolve(original);await pending;assert(!el('sound-original').src,'Discard inspection arriving after disconnect');
 assert(el('sound-apply').disabled);assert.equal(timers.size,0);assert.deepEqual(errors,['Ersetzt']);
 console.log('Sound PCM conversion, exact file selection, explicit confirmation, job polling and disconnect handling passed.');
})().catch(e=>{console.error(e);process.exit(1);});
