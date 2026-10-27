const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('inca/index.html','utf8');let code=html.match(/<script>([\s\S]*)<\/script>/)[1].replace(/archive\(\);\s*$/,'');
const elements=new Map();const get=k=>{if(!elements.has(k))elements.set(k,{value:'',textContent:'',innerHTML:'',hidden:false,addEventListener(){}});return elements.get(k)};
const context=vm.createContext({document:{querySelector:get,querySelectorAll:()=>[]},window:{addEventListener(){}},console});vm.runInContext(code,context);
vm.runInContext(`rows=[{id:1,line:2,'INSEGNAMENTO':'Fisiologia','SSD INSEGNAMENTO':'BIO/09','TIPOLOGIA':'Laurea','SEDE CORSO':'VERONA','CODICE CORSO':'001'},{id:2,line:3,'INSEGNAMENTO':'Agronomia','SSD INSEGNAMENTO':'AGR/15','TIPOLOGIA':'Master','SEDE CORSO':'ALTRA','CODICE CORSO':'002'}]`,context);
const filters=vm.runInContext('filters',context);
for(const key of ['TIPOLOGIA','SEDE CORSO','CODICE CORSO'])assert(filters.includes(key));

const run=s=>vm.runInContext(s,context);
run('resetFilters()');
const choose=(k,v,on=true)=>run(`toggleFilter(${filters.indexOf(k)},${JSON.stringify(v)},${on})`);
const count=n=>assert.match(get('#count').textContent,new RegExp('^'+n+' risultati'));
get('#search').value='fisiologia';choose('SSD INSEGNAMENTO','AGR/15');count(0);
choose('SSD INSEGNAMENTO','BIO/09');count(1);assert.match(get('#activefilters').textContent,/oppure/);
get('#search').value='';run('renderRows()');count(2);
choose('SEDE CORSO','VERONA');count(1);
choose('SEDE CORSO','ALTRA');count(2);
choose('CODICE CORSO','001');count(1);
choose('CODICE CORSO','001',false);count(2);
run(`clearFilter(${filters.indexOf('SEDE CORSO')})`);count(2);assert.equal(get('#fsummary'+filters.indexOf('SEDE CORSO')).textContent,'Tutti');
run('selected.add(1);resetFilters()');count(2);assert.equal(run('selected.size'),1);
choose('DIPARTIMENTO (DI RIFERIMENTO)','');count(2);assert.match(get('#activefilters').textContent,/Non compilato/);
run("rows[0]['SEDE CORSO']='  VERONA  ';rows[0]['TIPOLOGIA']='Laurea   magistrale'");
choose('SEDE CORSO','VERONA');choose('TIPOLOGIA','Laurea magistrale');count(1);
get('#search').value='inesistente';run('renderRows()');count(0);assert.equal(get('#emptyresults').hidden,false);
run('resetFilters()');count(2);assert.equal(get('#emptyresults').hidden,true);
// Linked facets: same-filter OR choices remain; other facets are constrained.
run(`rows=[
 {id:1,'DIPARTIMENTO (DI RIFERIMENTO)':'D1','CODICE CORSO':'001','SEDE CORSO':'A','INSEGNAMENTO':'Fisiologia'},
 {id:2,'DIPARTIMENTO (DI RIFERIMENTO)':'D1','CODICE CORSO':'002','SEDE CORSO':'B','INSEGNAMENTO':'Chimica'},
 {id:3,'DIPARTIMENTO (DI RIFERIMENTO)':'D2','CODICE CORSO':'003','SEDE CORSO':'C','INSEGNAMENTO':'Chimica'}];resetFilters()`);
const options=k=>Array.from(run('facetOptions()')[filters.indexOf(k)]).sort();
choose('DIPARTIMENTO (DI RIFERIMENTO)','D1');
assert.deepEqual(options('CODICE CORSO'),['001','002']);assert.deepEqual(options('SEDE CORSO'),['A','B']);
assert.deepEqual(options('DIPARTIMENTO (DI RIFERIMENTO)'),['D1','D2']);
choose('CODICE CORSO','001');assert.deepEqual(options('CODICE CORSO'),['001','002']);assert.deepEqual(options('SEDE CORSO'),['A']);
choose('CODICE CORSO','002');count(2);
get('#search').value='chimica';run('renderRows()');count(1);assert.deepEqual(options('SEDE CORSO'),['B']);
assert.deepEqual(options('CODICE CORSO'),['002']);
// Previously selected incompatible choices remain visible and removable.
const label={hidden:true},span={textContent:''},input={value:'001',closest:()=>label,nextElementSibling:span};
context.document.querySelectorAll=selector=>selector===`input[data-filter="${filters.indexOf('CODICE CORSO')}"]`?[input]:[];
run('updateFilterOptions()');assert.equal(label.hidden,false);assert.equal(input.checked,true);assert.match(span.textContent,/nessuna corrispondenza/);
choose('CODICE CORSO','001',false);assert.equal(label.hidden,true);
run('resetFilters()');count(3);assert.equal(label.hidden,false);assert.deepEqual(options('CODICE CORSO'),['001','002','003']);
context.document.querySelectorAll=()=>[];
// Exercise menu generation and source switching with no imported archive.
get('#source').value='';
run('loadRows()').then(()=>{count(0);assert.match(get('#filterbox').innerHTML,/multifilter/);assert.equal(run('filterSelections.every(s=>s.size===0)'),true);console.log('PASS multiple choices OR, cross-filter AND, search, empty values, reset and source switching');}).catch(e=>{console.error(e);process.exitCode=1});
