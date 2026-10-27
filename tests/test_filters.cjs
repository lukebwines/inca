const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('inca/index.html','utf8');let code=html.match(/<script>([\s\S]*)<\/script>/)[1].replace(/archive\(\);\s*$/,'');
const elements=new Map();const get=k=>{if(!elements.has(k))elements.set(k,{value:'',textContent:'',innerHTML:'',hidden:false,addEventListener(){}});return elements.get(k)};
const context=vm.createContext({document:{querySelector:get},window:{addEventListener(){}},console});vm.runInContext(code,context);
vm.runInContext(`rows=[{id:1,line:2,'INSEGNAMENTO':'Fisiologia','SSD INSEGNAMENTO':'BIO/09','TIPOLOGIA':'Laurea','SEDE CORSO':'VERONA','CODICE CORSO':'001'},{id:2,line:3,'INSEGNAMENTO':'Agronomia','SSD INSEGNAMENTO':'AGR/15','TIPOLOGIA':'Master','SEDE CORSO':'ALTRA','CODICE CORSO':'002'}]`,context);
const filters=vm.runInContext('filters',context);
for(const key of ['TIPOLOGIA','SEDE CORSO','CODICE CORSO'])assert(filters.includes(key));
get('#search').value='fisiologia';get('#f'+filters.indexOf('SSD INSEGNAMENTO')).value='AGR/15';vm.runInContext('renderRows()',context);assert.match(get('#count').textContent,/^0 risultati/);assert.equal(get('#emptyresults').hidden,false);assert.match(get('#activefilters').textContent,/AGR\/15/);
get('#f'+filters.indexOf('SSD INSEGNAMENTO')).value='';vm.runInContext('renderRows()',context);assert.match(get('#count').textContent,/^1 risultati/);
for(const [key,value] of [['TIPOLOGIA','Laurea'],['SEDE CORSO','VERONA'],['CODICE CORSO','001']])get('#f'+filters.indexOf(key)).value=value;
vm.runInContext('renderRows()',context);assert.match(get('#count').textContent,/^1 risultati/);assert.match(get('#table').innerHTML,/001/);
vm.runInContext('resetFilters()',context);assert.match(get('#count').textContent,/^2 risultati/);assert.equal(get('#search').value,'');assert.equal(get('#emptyresults').hidden,true);
console.log('PASS filters, combined search, empty state, course code and reset');

vm.runInContext("rows[0]['SEDE CORSO']='  VERONA \u00a0 ';rows[0]['TIPOLOGIA']='Laurea   magistrale'",context);
get('#f'+filters.indexOf('SEDE CORSO')).value='VERONA';get('#f'+filters.indexOf('TIPOLOGIA')).value='Laurea magistrale';vm.runInContext('renderRows()',context);assert.match(get('#count').textContent,/^1 risultati/);
console.log('PASS whitespace normalization without changing source records');
