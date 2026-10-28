const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('inca/index.html','utf8');
const elements=new Map();
function parse(fragment){for(const match of fragment.matchAll(/\bid="([^"]+)"/g)){const id=match[1];if(!elements.has(id))elements.set(id,{addEventListener(){},value:'',hidden:false,textContent:'',_html:'',get innerHTML(){return this._html},set innerHTML(value){this._html=value;parse(value)}})}}
parse(html.split('<script>')[0]);
const context=vm.createContext({document:{querySelector:s=>elements.get(s.slice(1))||null,querySelectorAll:()=>[]},window:{addEventListener(){}},console});
const code=html.match(/<script>([\s\S]*)<\/script>/)[1].replace(/archive\(\);\s*$/,'');vm.runInContext(code,context);
const run=s=>vm.runInContext(s,context);
(async()=>{
 for(const [role,external] of [['admin',false],['admin',true],['operator',true]]){
  context.fixture={imports:[],practices:[],edit:[],auth:{username:'Test',role,external}};
  run('api=async()=>fixture');await run('archive()');
  assert.match(elements.get('view').innerHTML,/Archivio delle coperture/);
  assert.equal(elements.get('backupbutton').hidden,role!=='admin');
  assert.equal(elements.get('accountmenu').innerHTML.includes('Utenti'),role==='admin');
  assert.equal(elements.get('accountmenu').innerHTML.includes('Esci'),external);
  await run('practices()');assert.match(elements.get('view').innerHTML,/Nessuna pratica/);
 }
 context.fixture=[];await run('usersPage()');assert(elements.has('newuser'));assert(elements.has('usererror'));
 console.log('PASS real HTML navigation IDs, archive/practices for each role, initial user form');
})().catch(e=>{console.error(e);process.exitCode=1});
