'use strict';
(function(root){
 const secrets=new Set(),entries=[];
 function scrub(value){let s=String(value??'');for(const token of secrets)s=s.split(token).join('[REDACTED]');return s.replace(/([#?&]pair=)[^&\s"']+/g,'$1[REDACTED]');}
 function redact(value){if(typeof value==='string')return scrub(value);if(Array.isArray(value))return value.map(redact);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,/token|password|source|authorization/i.test(k)?'[OMITTED]':redact(v)]));return value;}
 function record(event,details={}){entries.push({time:new Date().toISOString(),event:scrub(event),details:redact(details)});if(entries.length>1000)entries.splice(0,entries.length-1000);try{root.sessionStorage?.setItem('mythic-diagnostics-v1',JSON.stringify(entries));}catch{}}
 try{const saved=JSON.parse(root.sessionStorage?.getItem('mythic-diagnostics-v1')||'[]');if(Array.isArray(saved))entries.push(...saved.slice(-999).map(redact));}catch{}
 root.mwDiagnostics={record,secret:value=>{if(value)secrets.add(value);},snapshot:()=>JSON.parse(JSON.stringify(entries.map(redact)))};
 root.addEventListener?.('error',e=>record('javascript.error',{message:e.message,file:e.filename,line:e.lineno,stack:e.error?.stack}));
 root.addEventListener?.('unhandledrejection',e=>record('javascript.rejection',{message:e.reason?.message||String(e.reason),stack:e.reason?.stack}));
 record('page.loaded',{origin:root.location?.origin,secure:root.isSecureContext,userAgent:root.navigator?.userAgent,online:root.navigator?.onLine});
 if(typeof module!=='undefined')module.exports=root.mwDiagnostics;
})(typeof window==='undefined'?globalThis:window);
