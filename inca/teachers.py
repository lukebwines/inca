"""Versioned teaching-load references. Never add proposal hours to imported loads."""
import json, re, math, io, unicodedata, hashlib, datetime
import xlrd
FIELDS=['NOME','COGNOME','SSD','SSD SETTORE NUOVO','DIPARTIMENTO/SCUOLA','QUALIFICA','ORE POTENZIALE','ORE CARICO PREVENTIVO','ORE CARICO CONSUNTIVO']
def norm(v):return ' '.join(unicodedata.normalize('NFKC',str(v or '')).casefold().replace('’',"'").split())
def key(r,coverage=False):return (norm(r.get('NOME DOCENTE' if coverage else 'NOME')),norm(r.get('COGNOME DOCENTE' if coverage else 'COGNOME')))
def init(c):
 c.executescript('CREATE TABLE IF NOT EXISTS teacher_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,year TEXT,reference_date TEXT,created TEXT,sha TEXT,body TEXT); CREATE TABLE IF NOT EXISTS practice_teachers(practice_id INTEGER PRIMARY KEY,body TEXT);')
def current(c):
 r=c.execute('select * from teacher_reports order by id desc limit 1').fetchone()
 if not r:return None
 r=dict(r);r['rows']=json.loads(r.pop('body'));return r
def parse(raw):
 b=xlrd.open_workbook(file_contents=raw,logfile=io.StringIO());s=b.sheet_by_index(0)
 headers=[str(v).strip() for v in s.row_values(0)]
 if len(set(headers))!=len(headers) or not set(FIELDS).issubset(headers):raise ValueError('Il report docenti deve contenere le nove colonne attese, senza intestazioni duplicate.')
 rows=[];seen=set()
 for i in range(1,s.nrows):
  vals=s.row_values(i)
  if not any(v!='' for v in vals):continue
  r={f:vals[headers.index(f)] for f in FIELDS}
  if not all(key(r)):raise ValueError(f'Nome o cognome assente alla riga {i+1}.')
  if key(r) in seen:raise ValueError(f'Nome e cognome duplicati alla riga {i+1}: risolvere prima di importare.')
  seen.add(key(r))
  for f in FIELDS[-3:]:
   if r[f]=='':r[f]=None;continue
   try:r[f]=float(str(r[f]).replace(',','.'))
   except ValueError:raise ValueError(f'Ore non numeriche alla riga {i+1}.')
   if not math.isfinite(r[f]) or r[f]<0:raise ValueError(f'Ore non valide alla riga {i+1}.')
  r.update(id=len(rows)+1,matricola='',placeholder='futuro' in ' '.join(key(r)))
  rows.append(r)
 if not rows:raise ValueError('Report vuoto: archivio precedente conservato.')
 return rows
def replace(c,raw,name,year,date,created):
 if not re.fullmatch(r'\d{4}/\d{4}',year) or int(year[5:])!=int(year[:4])+1:raise ValueError('Anno di riferimento non valido: usare 2026/2027.')
 if date:datetime.date.fromisoformat(date)
 rows=parse(raw)
 # Each upload requires identity confirmation again: never transfer stale mappings silently.
 c.execute('insert into teacher_reports(name,year,reference_date,created,sha,body) values(?,?,?,?,?,?)',(name,year,date,created,hashlib.sha256(raw).hexdigest(),json.dumps(rows)))
 c.execute('delete from teacher_reports where id<>(select max(id) from teacher_reports)')
 return len(rows)
def candidates(c,report):
 index={}
 # Whole active coverage report: specialty convention n-1 does not filter identities.
 for row in c.execute('select body from records where import_id=(select max(id) from imports)'):
  r=json.loads(row['body']);m=str(r.get('MATRICOLA DOCENTE','')).strip()
  if not m:continue
  group=index.setdefault(key(r,True),{})
  item=group.setdefault(m,{'matricola':m,'details':set()})
  item['details'].add(' · '.join(str(r.get(k,'') or '') for k in ['QUALIFICA DOCENTE','DIPARTIMENTO AFFERENZA DOCENTE','CODICE SSD DOCENTE']))
 for r in report['rows']:
  r['candidates']=[] if r['placeholder'] else [{'matricola':m,'details':' / '.join(sorted(v['details']))} for m,v in index.get(key(r),{}).items()]
 return report
def link(c,q):
 report=current(c)
 if not report or report['id']!=int(q['report_id']):raise ValueError('Report aggiornato: riaprire l’elenco docenti.')
 candidates(c,report);r=next((r for r in report['rows'] if r['id']==int(q['teacher_id'])),None)
 if not r:raise ValueError('Docente non trovato.')
 m=str(q.get('matricola',''))
 if m and m not in {x['matricola'] for x in r['candidates']}:raise ValueError('Matricola non presente tra i candidati del docente.')
 if m and any(x['id']!=r['id'] and x['matricola']==m for x in report['rows']):raise ValueError('Matricola già collegata a un altro docente.')
 r['matricola']=m
 for x in report['rows']:x.pop('candidates',None)
 c.execute('update teacher_reports set body=? where id=?',(json.dumps(report['rows']),report['id']))
def attach(c,pid,year=None):
 report=current(c)
 if not report:raise ValueError('Importare prima il report docenti.')
 years={str(json.loads(x['body']).get('ANNO ACCADEMICO','')) for x in c.execute('select body from changes where practice_id=?',(pid,))}
 if years!={report['year']}:raise ValueError('Anno degli incarichi diverso dall’archivio docenti: verificare il report.')
 if c.execute('select 1 from practice_teachers where practice_id=?',(pid,)).fetchone():raise ValueError('Il riferimento docenti è già conservato nella pratica e non viene sovrascritto.')
 c.execute('insert into practice_teachers values(?,?)',(pid,json.dumps(report)))
def snapshot(c,pid):
 row=c.execute('select body from practice_teachers where practice_id=?',(pid,)).fetchone()
 return json.loads(row['body']) if row else None
def select_teacher(c,pid,tid,r):
 snap=snapshot(c,pid)
 t=next((x for x in (snap or {}).get('rows',[]) if x['id']==int(tid)),None)
 if not t or not t['matricola'] or t['placeholder']:raise ValueError('Selezionare un docente con matricola confermata nel riferimento della pratica.')
 r.update({'NOME DOCENTE':t['NOME'],'COGNOME DOCENTE':t['COGNOME'],'MATRICOLA DOCENTE':t['matricola'],'DIPARTIMENTO AFFERENZA DOCENTE':t['DIPARTIMENTO/SCUOLA'],'CODICE SSD DOCENTE':t['SSD'],'CODICE SSD DOCENTE NUOVO':t['SSD SETTORE NUOVO'],'QUALIFICA DOCENTE':t['QUALIFICA']})
 # Do not keep another person's identifiers or workload on a changed assignment.
 for k in ['CF DOCENTE','CODICE GIA','SATURAZIONE DOCENTE A PREVENTIVO','SATURAZIONE DOCENTE A CONSUNTIVO','POTENZIALE','DATA NASCITA','LUOGO NASCITA','PROV NASCITA','NAZIONE NASCITA','COMUNE RESIDENZA','PROV RESIDENZA','INDIRIZZO RESIDENZA','FRAZIONE RESIDENZA','CAP RESIDENZA']:r[k]=''
def summaries(snap,items):
 if not snap:return []
 out=[f"Archivio docenti di riferimento: {snap['name']} · a.a. {snap['year']} · data report: {snap['reference_date'] or '[DA VERIFICARE]'} · acquisito {snap['created']}. Carichi in ore; variazioni non sommate automaticamente."]
 seen=set()
 for item in items:
  for phase in ['before','after']:
   r=item[phase];k=key(r,True)
   if not all(k) or k in seen:continue
   seen.add(k);found=[t for t in snap['rows'] if key(t)==k and not t['placeholder']]
   if len(found)!=1:
    out.append(f"{' '.join(str(r.get(f,'')) for f in ['NOME DOCENTE','COGNOME DOCENTE'])}: non presente nel riferimento docenti [DA VERIFICARE].");continue
   t=found[0];fmt=lambda v:'[DA VERIFICARE]' if v is None or v=='' else str(v)
   msg=f"{t['NOME']} {t['COGNOME']}: potenziale {fmt(t['ORE POTENZIALE'])}; preventivo {fmt(t['ORE CARICO PREVENTIVO'])}; consuntivo {fmt(t['ORE CARICO CONSUNTIVO'])} ore. "
   msg+='Matricola confermata: '+t['matricola']+'.' if t['matricola'] else 'Abbinamento per nome e cognome da confermare.'
   before=[x['before'].get('SATURAZIONE DOCENTE A PREVENTIVO') for x in items if key(x['before'],True)==k]
   vals=sorted({float(v) for v in before if isinstance(v,(int,float))})
   if vals:
    msg+=' Carico premodifica nelle coperture: '+', '.join(map(str,vals))+' ore.'
    if t['ORE CARICO PREVENTIVO'] is not None and any(abs(v-t['ORE CARICO PREVENTIVO'])>.001 for v in vals):msg+=' DIFFERENZA TRA REPORT: verificare se la modifica è già recepita.'
   changes=[]
   for phase,sign in [('before',-1),('after',1)]:
    for x in items:
     if key(x[phase],True)==k:
      value=x[phase].get('TOT ORE PREVISTE')
      changes.append(sign*value if isinstance(value,(int,float)) else None)
   if changes and all(v is not None for v in changes):
    delta=round(sum(changes),10)
    msg+=f' Variazione delle ore degli incarichi nella pratica: {delta:+g} (non sommata al carico del report).'
   elif changes:msg+=' Variazione delle ore degli incarichi: [DA VERIFICARE].'
   out.append(msg)
 return out
