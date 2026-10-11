const assert=require('node:assert/strict');const {createMythicHandoff}=require('../dist/handoff.js');
const channels=[];class Channel{constructor(){channels.push(this);}postMessage(data){for(const c of channels)if(c!==this)queueMicrotask(()=>c.onmessage({data:structuredClone(data)}));}}
(async()=>{
 let received=[],focused=0;
 const existing=createMythicHandoff({Channel,onPair:t=>received.push(t),connected:()=>true,focus:()=>focused++});
 const other=createMythicHandoff({Channel,onPair:t=>{throw Error('wrong tab');},connected:()=>false,focus(){}});
 const opening=createMythicHandoff({Channel,onPair(){},connected:()=>false,focus(){}});
 const token='fixture_pair_code_1234567890';assert.equal(await opening.offer(token),true);assert.deepEqual(received,[token]);assert.equal(focused,1);
 channels.length=0;const alone=createMythicHandoff({Channel,onPair(){},connected:()=>false,focus(){}});assert.equal(await alone.offer(token),false);
 assert.equal(await createMythicHandoff({Channel:null}).offer(token),false);
 console.log('Existing dashboard receives pairing; connected tab wins; no-tab and unsupported-browser fallback pass.');
})().catch(e=>{console.error(e);process.exit(1);});
