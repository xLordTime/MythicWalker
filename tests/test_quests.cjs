const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {validateQuestPlan,questMatch}=require('../dist/quests.js');
const rows=[{id:'7',name:'Same name'},{id:'8',name:'Same name'},{id:'7',goal_id:'3',name:'Return visit'}];
const plan=validateQuestPlan({version:1,quests:rows});
assert.equal(questMatch(plan.quests,{status:'ready',active_id:'7',goal_id:'3'}),2);
assert.equal(questMatch(plan.quests,{status:'ready',active_id:'7',goal_id:'4'}),0);
assert.equal(questMatch(plan.quests,{status:'loading',active_id:'7'}),-1);
assert.equal(questMatch([{id:'7'},{id:'7'}],{status:'ready',active_id:'7'}),-1);
assert.equal(questMatch(plan.quests,{status:'ready',active_id:'99'}),-1);
assert.throws(()=>validateQuestPlan({version:1,quests:[{id:7,name:'X'}]}));
assert.throws(()=>validateQuestPlan({version:1,quests:[rows[0],rows[0]]}));
assert.throws(()=>validateQuestPlan({version:1,quests:[{id:'7',name:'X',goal_id:'<script>'}]}));
const elements=new Map(),store=new Map(),timers=new Map();let chosen=['42'],requests=[],timerId=0;
function el(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,innerHTML:'',textContent:'',hidden:false,disabled:false});return elements.get(id);}
const context={module:{exports:{}},console,URL,Date,localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},document:{getElementById:el},window:{},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),createAccountPicker:()=>({ids:()=>chosen,render(){},closed(){chosen=[];}})};
vm.createContext(context);vm.runInContext(fs.readFileSync('dist/quests.js','utf8'),context);
const state={connected:true,questAvailable:true,clients:[{id:'42',hooked:true},{id:'99',hooked:true}]};
const tracker=context.module.exports.createQuests({state,command:(op,args)=>new Promise((resolve,reject)=>requests.push({op,args,resolve,reject})),toast(){},download(){}});
const flush=()=>new Promise(r=>setImmediate(r));
function snapshot(id,quest='7'){return{id,status:'ready',active_id:quest,goal_id:'3',zone:'WizardCity/Commons',quests:[{id:quest,name:'<img onerror=attack()>',goals:[]}]};}
(async()=>{
 tracker.navigate('quests');assert.equal(requests.length,1);assert.equal(requests[0].op,'quest_status');
 tracker.render();assert.equal(requests.length,1,'No overlapping reads');
 chosen=['99'];tracker.render();requests[0].resolve(snapshot('42'));await flush();
 assert(!el('quests-current').innerHTML.includes('attack'),'Stale result discarded after account switch');
 const [tid,next]=[...timers.entries()].at(-1);timers.delete(tid);next();assert.equal(requests[1].args.ids[0],'99');
 requests[1].resolve(snapshot('99'));await flush();
 assert(el('quests-current').innerHTML.includes('&lt;img'));assert(!el('quests-current').innerHTML.includes('<img'));
 assert(el('quests-list').innerHTML.includes('aria-current="step"'));
 state.clients[1].hooked=false;tracker.render();assert(!el('quests-list').innerHTML.includes('aria-current="step"'));assert.equal(timers.size,0);
 state.clients[1].hooked=true;tracker.render();requests.at(-1).reject(Error('Memory read failed'));await flush();
 assert(el('quests-status').textContent.includes('Memory read failed'));assert(!el('quests-list').innerHTML.includes('aria-current="step"'));
 tracker.navigate('tools');assert.equal(timers.size,0);tracker.closed();
 console.log('Quest IDs, repeated phases, import bounds, escaping, client switching, unhook, read errors and polling passed.');
})().catch(e=>{console.error(e);process.exit(1);});
