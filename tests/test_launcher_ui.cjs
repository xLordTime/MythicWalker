const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('bridge/launcher_web/index.html','utf8'),elements=new Map();let intervals=[],requests=[],unlocked=false,rows=[],pendingDelete=false;
class Element{
 constructor(tag='div'){this.tagName=tag;this.value='';this.hidden=false;this.disabled=false;this.children=[];this.dataset={};this.classList={toggle(){}};}
 set id(v){this._id=v;elements.set(v,this);}get id(){return this._id;}
 replaceChildren(...args){this.children=args;}append(...args){this.children.push(...args);}focus(){}reset(){for(const id of ['account-id','account-name','account-user','account-password'])elements.get(id).value='';}showModal(){pendingDelete=true;}close(){pendingDelete=false;}
}
for(const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"[^>]*>/g)){const e=new Element(m[1]);e.id=m[2];}
const state=()=>({unlocked,accounts:rows,regions:{de:'Deutschland'},settings:{paths:{de:'C:/Game'},login_wait:5},folder:'C:/Local/WizQLauncher',legacy:true,imported:false,progress:{running:false,message:'Bereit',done:0,total:0},processes:[]});
const context={document:{getElementById:id=>{assert(elements.has(id),'Missing '+id);return elements.get(id);},createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text}),querySelectorAll:()=>[]},location:{hash:'#ticket='+'A'.repeat(43),pathname:'/'},history:{replaceState(){}},window:{addEventListener(){}},setInterval:fn=>intervals.push(fn),setTimeout,clearTimeout,URLSearchParams,AbortController,console,
 fetch:async(url,options)=>{assert(url.startsWith('/api/'));assert.equal(options.credentials,'omit');const args=JSON.parse(options.body);requests.push({url,args});let data;
 if(url.endsWith('/exchange'))data={session:'local-only-session'};
 else{assert.equal(options.headers.Authorization,'Bearer local-only-session');if(url.endsWith('/unlock'))unlocked=true;if(url.endsWith('/lock'))unlocked=false;if(url.endsWith('/save'))rows=[{id:'1'.repeat(32),name:args.name,username:args.username,region:args.region}];if(url.endsWith('/delete'))rows=[];data=url.endsWith('/import')?{added:0}:state();}
 return {ok:true,status:200,json:async()=>data};}};
vm.createContext(context);vm.runInContext(fs.readFileSync('bridge/launcher_web/launcher.js','utf8'),context);
const el=id=>elements.get(id);
(async()=>{
 await new Promise(r=>setTimeout(r,0));assert.equal(el('unlock').disabled,false);
 await el('unlock').onclick();assert.equal(el('workspace').hidden,false);assert.equal(el('path-de').value,'C:/Game');
 el('new-account').onclick();el('account-name').value='<untrusted>';el('account-user').value='user';el('account-password').value='TOP-SECRET';el('account-region').value='de';
 await el('account-form').onsubmit({preventDefault(){}});assert.equal(el('account-password').value,'');assert.equal(el('account-form').hidden,true);
 assert.equal(rows.length,1);assert(!JSON.stringify(el('accounts').children).includes('TOP-SECRET'));
 const row=el('accounts').children[0];assert.equal(row.children[0].children[1].textContent,'<untrusted>');
 await row.children[2].onclick();assert(pendingDelete);assert.equal(rows.length,1);await el('delete-confirm').onclick();assert.equal(rows.length,0);assert(!pendingDelete);
 await el('lock').onclick();assert.equal(el('workspace').hidden,true);
 assert(requests.some(r=>r.url==='/api/save'&&r.args.password==='TOP-SECRET'));
 console.log('Local UI unlock, safe account rendering, credential clearing, explicit delete and lock passed.');
})().catch(e=>{console.error(e);process.exit(1);});
