const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
function el(id){if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',disabled:false});return elements.get(id);}
const ctx={document:{getElementById:el},console};vm.createContext(ctx);vm.runInContext(fs.readFileSync('dist/accounts.js','utf8'),ctx);
(async()=>{
 const state={clients:[{id:'11',pid:11,title:'A <test>',hooked:true,zone:'Zone A'},{id:'22',pid:22,title:'B',hooked:true,zone:'Zone B'}],connected:true,selected:new Set(['11'])};
 const calls=[];let stopDone=false,resolveStop,rejectStop;
 const account=ctx.createAccountPicker({prefix:'test',state,command:async(op,args)=>calls.push([op,args]),toast:m=>calls.push(m),beforeChange:()=>new Promise((resolve,reject)=>{resolveStop=()=>{stopDone=true;resolve();};rejectStop=reject;})});
 account.adopt('11');account.render();assert(el('test-account').innerHTML.includes('A &lt;test&gt;'));
 const changing=account.choose('22');assert.deepEqual([...account.ids()],['11']);assert(account.busy);resolveStop();await changing;assert(stopDone);assert.deepEqual([...account.ids()],['22']);assert.deepEqual([...state.selected],['11']);assert(el('test-account-info').textContent.includes('Zone B'));
 const failing=account.choose('11');rejectStop(Error('Restore failed'));await failing;assert.deepEqual([...account.ids()],['22']);assert(calls.includes('Restore failed'));
 state.clients=state.clients.filter(c=>c.id==='11');account.render();assert.deepEqual([...account.ids()],[],'Disappearing client must not silently retarget');
 account.closed();state.clients=[];account.render();assert.deepEqual([...account.ids()],[]);
 console.log('Account switching waits for cleanup, preserves global selection, escapes titles and rejects silent retargeting.');
})();
