const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('inca/index.html','utf8');
const elements=new Map();
function parse(fragment){for(const match of fragment.matchAll(/\bid="([^"]+)"/g)){const id=match[1];if(!elements.has(id))elements.set(id,{addEventListener(){},showModal(){},close(){},insertAdjacentHTML(position,value){this.innerHTML+=value},value:'',hidden:false,textContent:'',_html:'',get innerHTML(){return this._html},set innerHTML(value){this._html=value;parse(value)}})}}
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
 run("S.edit=['CFU'];active={practice:{title:'Test',notes:'',created:''},items:[{id:1,before:{CFU:1,'SATURAZIONE DOCENTE A PREVENTIVO':125.5},after:{CFU:2,'SATURAZIONE DOCENTE A PREVENTIVO':999},warnings:[],history:[]}]}");
 run('drawPractice()');assert.match(elements.get('items').innerHTML,/premodifica:<\/strong> 125.5/);
 elements.get('only').checked=true;run('drawItems()');assert.match(elements.get('items').innerHTML,/premodifica:<\/strong> 125.5/);
 run("active.items[0].before['SATURAZIONE DOCENTE A PREVENTIVO']=0;drawItems()");assert.match(elements.get('items').innerHTML,/premodifica:<\/strong> 0/);
 run("delete active.items[0].before['SATURAZIONE DOCENTE A PREVENTIVO'];drawItems()");assert.match(elements.get('items').innerHTML,/premodifica:<\/strong> \[DA VERIFICARE\]/);
 run("active.practice.title='Cardiologia 2026-2027';active.practice.id=1");assert.equal(run('practiceFilename()'),'Cardiologia 2026-2027');
 run("active.practice.title='Test: titolo?'");assert.equal(run('practiceFilename()'),'Test_ titolo_');
 run("active.items[0].kind='new';active.items[0].after.MODULO='Modulo nuovo';active.items[0].note='Nota <test>';drawItems()");
 assert.match(elements.get('items').innerHTML,/Nuova copertura proposta/);assert.match(elements.get('items').innerHTML,/Modulo nuovo/);assert.match(elements.get('items').innerHTML,/Nota &lt;test&gt;/);
 run("active.items[0].kind='existing';active.items[0].after['TOT ORE PREVISTE']=10;active.items[0].after.OREPREVLEZ=10;splitForm(1)");
 assert(elements.has('splitform'));assert(elements.has('splitnote'));assert.equal(typeof elements.get('splitform').onsubmit,'function');
 context.fixture=[];await run('usersPage()');assert(elements.has('newuser'));assert(elements.has('usererror'));
 context.fixture={imports:[],practices:[],edit:[],auth:{username:'Test',role:'admin',external:false}};
 context.teacherFixture={id:1,name:'synthetic.xls',year:'2026/2027',reference_date:'',created:'TEST',rows:[{id:1,NOME:'Nome',COGNOME:'<Prova>',matricola:'000123',placeholder:false,candidates:[],'ORE POTENZIALE':120,'ORE CARICO PREVENTIVO':80,'ORE CARICO CONSUNTIVO':0}]};
 run("api=async path=>path==='/state'?fixture:teacherFixture");await run('teachersPage()');
 assert(elements.has('teacherupload'));assert.match(elements.get('teacherlist').innerHTML,/&lt;Prova&gt;/);assert.match(elements.get('teachercount').textContent,/1 abbinamenti confermati/);
 run('active.teacher_reference=teacherFixture;active.teacher_summary=["Carico <test>"];active.teacher_report_newer=true;drawPractice()');
 assert.match(elements.get('view').innerHTML,/Carico &lt;test&gt;/);assert.match(run('teacherPicker()'),/000123/);assert.match(run('allocationPicker()'),/000123/);
 console.log('PASS real HTML navigation IDs, archive/practices for each role, initial user form');
})().catch(e=>{console.error(e);process.exitCode=1});
