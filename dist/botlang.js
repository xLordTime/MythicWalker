'use strict';
function compileBot(source,library={},parseCommand){
 if(typeof source!=='string'||source.length>65536)throw Error('Bot zu lang (max. 64 KB).');
 if(!library||Array.isArray(library)||typeof library!=='object'||Object.keys(library).length>100)throw Error('Maximal 100 Bibliotheksblöcke.');
 const name=/^[A-Za-z_][A-Za-z0-9_]{0,63}$/;let total=0;const blocks=Object.create(null);
 function condition(s,line){const m=s.match(/^(not\s+)?(?:(any|mass|p[1-9]\d*)\s+)?(incombat|loading)$/);if(!m)throw Error(`Zeile ${line}: Bedingung nicht unterstützt: ${s}`);return {not:!!m[1],target:m[2]||'any',test:m[3]};}
 function parse(code,libName){
  if(typeof code!=='string'||(libName&&code.length>16000))throw Error('Bibliotheksblock zu lang (max. 16 KB).');
  const lines=code.split(/\r?\n/).flatMap((raw,i)=>{const s=raw.trim();return !s||s.startsWith('#')?[]:/^}\s*else\s*{$/.test(s)?[[i+1,'}'],[i+1,'else {']]:[[i+1,s]];});let pos=0;const local=Object.create(null);
  function body(depth=0,loopDepth=0,closing=false){const nodes=[];if(depth>12)throw Error('Maximal 12 verschachtelte Ebenen.');
   while(pos<lines.length){const [line,s]=lines[pos++];if(++total>2000)throw Error('Maximal 2000 Anweisungen einschließlich Bibliothek.');if(s==='}'){if(!closing)throw Error(`Zeile ${line}: Unerwartete Klammer.`);return nodes;}
    let m=s.match(/^block\s+([A-Za-z_][A-Za-z0-9_]{0,63})\s*{$/);if(m){if(depth)throw Error('Blöcke nur auf oberster Ebene definieren.');if(Object.hasOwn(local,m[1]))throw Error('Block doppelt definiert: '+m[1]);local[m[1]]=body(depth+1,0,true);continue;}
    m=s.match(/^(times\s+(\d+)|loop|while\s+(.+)|until\s+(.+)|if\s+(.+))\s*{$/);if(m){const kind=s.split(/\s/)[0],node={op:kind,line};if(kind==='times'){node.count=Number(m[2]);if(node.count<1||node.count>999999)throw Error('Wiederholungen: 1 bis 999999.');}else if(['if','while','until'].includes(kind))node.condition=condition((m[5]||m[3]||m[4]).trim(),line);node.body=body(depth+1,loopDepth+(kind!=='if'),true);if(!node.body.length)throw Error(`Zeile ${line}: Leerer Block.`);if(kind==='if'&&lines[pos]?.[1]==='else {'){pos++;node.else=body(depth+1,loopDepth,true);}nodes.push(node);continue;}
    m=s.match(/^call\s+([A-Za-z_][A-Za-z0-9_]{0,63})$/);if(m){nodes.push({op:'call',name:m[1],line});continue;}
    if(['break','exitloop'].includes(s)){if(!loopDepth)throw Error(`Zeile ${line}: break benötigt eine Schleife.`);nodes.push({op:'break',line});continue;}
    const statement=/^(mass|p[1-9]\d*|sleep)\s/.test(s)?s:'mass '+s;
    m=statement.match(/^(mass|p[1-9]\d*)\s+(tp closestmob|waitforzonechange completion)$/);if(m){nodes.push({op:m[2]==='tp closestmob'?'closest_mob':'wait_zone',target:m[1],line,timeout:120});continue;}
    let node;try{node=parseCommand(statement)[0];}catch(e){throw Error(`Zeile ${line}: ${e.message}`);}node.line=line;nodes.push(node);
   }if(closing)throw Error('Block nicht geschlossen.');return nodes;
  }
  const nodes=body();if(libName){if(nodes.length&&Object.keys(local).length)throw Error('Ein Bibliothekseintrag enthält entweder einen Block oder dessen Inhalt.');if(Object.keys(local).length){if(Object.keys(local).length!==1||!Object.hasOwn(local,libName))throw Error('Blockname muss dem Bibliotheksnamen entsprechen: '+libName);return local[libName];}return nodes;}return {nodes,local};
 }
 for(const [key,code] of Object.entries(library)){if(!name.test(key))throw Error('Ungültiger Bibliotheksname.');blocks[key]=parse(code,key);}
 const {nodes,local}=parse(source);Object.assign(blocks,local);if(!nodes.length)throw Error('Der Bot enthält keine ausführbaren Anweisungen.');
 function* calls(seq){for(const n of seq){if(n.op==='call')yield n.name;yield* calls(n.body||[]);yield* calls(n.else||[]);}}
 for(const seq of [nodes,...Object.values(blocks)])for(const key of calls(seq))if(!Object.hasOwn(blocks,key))throw Error('Unbekannter Block: '+key);
 const depths=new Map();function cycle(key,active){if(active.includes(key))throw Error('Rekursiver Blockaufruf: '+[...active,key].join(' → '));if(depths.has(key))return depths.get(key);let length=1;for(const other of calls(blocks[key]))length=Math.max(length,1+cycle(other,[...active,key]));if(length>16)throw Error('Maximal 16 verschachtelte Blockaufrufe.');depths.set(key,length);return length;}Object.keys(blocks).forEach(key=>cycle(key,[]));
 return {body:nodes,blocks,instructions:total};
}
function* botNodes(program){function* walk(seq){for(const n of seq){yield n;yield* walk(n.body||[]);yield* walk(n.else||[]);}}yield* walk(program.body);for(const seq of Object.values(program.blocks))yield* walk(seq);}
async function interpretBot(program,execute,check,progress,yieldControl){let count=0;const BREAK=Symbol('break');async function visit(seq){for(const n of seq){await yieldControl();await progress(n,++count);if(n.op==='call')await visit(program.blocks[n.name]);else if(n.op==='break')throw BREAK;else if(n.op==='if')await visit(await check(n.condition)?n.body:(n.else||[]));else if(['times','loop','while','until'].includes(n.op)){let i=0;while(true){if(n.op==='times'&&i>=n.count)break;if(['while','until'].includes(n.op)&&(await check(n.condition))===(n.op==='until'))break;try{await visit(n.body);}catch(e){if(e===BREAK)break;throw e;}i++;await yieldControl();}}else await execute(n);}}await visit(program.body);}
if(typeof module!=='undefined')module.exports={compileBot,botNodes,interpretBot};
