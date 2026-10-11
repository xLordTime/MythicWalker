'use strict';
function createMythicHandoff({onPair,connected,focus,Channel=typeof BroadcastChannel==='undefined'?null:BroadcastChannel}){
 if(!Channel)return{offer:async()=>false};
 const channel=new Channel('mythicwalker-dashboard-v1'),id=String(Math.random()).slice(2),pending=new Map();let offering=false;
 channel.onmessage=({data:m})=>{
  if(!m||typeof m!=='object'||m.sender===id)return;
  if(m.kind==='discover'&&!offering)channel.postMessage({kind:'candidate',sender:id,request:m.request,connected:connected(),visible:typeof document!=='undefined'&&document.visibilityState==='visible'});
  if(m.kind==='candidate'&&pending.has(m.request))pending.get(m.request).candidates.set(m.sender,m);
  if(m.kind==='deliver'&&m.recipient===id&&/^[A-Za-z0-9_-]{20,100}$/.test(m.token||'')){
   onPair(m.token);focus();channel.postMessage({kind:'accepted',sender:id,request:m.request,recipient:m.sender});
  }
  if(m.kind==='accepted'&&m.recipient===id&&pending.has(m.request))pending.get(m.request).accepted=true;
 };
 return{async offer(token){
  offering=true;const request=id+'-'+Date.now(),row={candidates:new Map(),accepted:false};pending.set(request,row);
  channel.postMessage({kind:'discover',sender:id,request});await new Promise(resolve=>setTimeout(resolve,250));
  const candidates=[...row.candidates.values()].sort((a,b)=>Number(b.connected)-Number(a.connected)||Number(b.visible)-Number(a.visible));
  if(candidates.length){channel.postMessage({kind:'deliver',sender:id,recipient:candidates[0].sender,request,token});await new Promise(resolve=>setTimeout(resolve,300));}
  pending.delete(request);offering=false;return row.accepted;
 }};
}
if(typeof module!=='undefined')module.exports={createMythicHandoff};
