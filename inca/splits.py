"""Proposed teaching-hour redistribution; imported records are never changed."""
import json, math
import teachers
CONTEXT=['CDS','ANNO ACCADEMICO','TIPOLOGIA','SEDE CORSO','CODICE CORSO','CFU TOTALI INS','CODICE INS','TIPOEROGAZIONE','INSEGNAMENTO','CODICE UGOV','DISCRIMINANTE DI OI','MODULO','UL','DISCRIMINANTE MODULO','ANNO','TAF INSEGNAMENTO','FUORI PIANO','SSD INSEGNAMENTO','MOODLE','PERIODO INIZIO','PERIODO FINE']
HOURS=['OREPREVLEZ','OREPREVLAB','OREPREVESE','OREPREVSEM','OREPREVALTRO','OREPREVTIR']
def number(value):
 if value is None or value=='':raise ValueError('Indicare le ore mancanti prima di procedere.')
 try:v=float(str(value).replace(',','.'))
 except (TypeError,ValueError):raise ValueError('Ore non valide.')
 if not math.isfinite(v) or v<0:raise ValueError('Inserire ore non negative.')
 return v

def redistribute(db,now,q):
 allocations=q.get('allocations',[])
 if not isinstance(allocations,list) or not 1<=len(allocations)<=30:raise ValueError('Inserire da 1 a 30 destinatari.')
 prepared=[]
 for allocation in allocations:
  hours=number(allocation.get('hours'))
  surname=str(allocation.get('surname','')).strip();name=str(allocation.get('name','')).strip()
  if not surname or hours<=0:raise ValueError('Ogni destinatario richiede cognome e ore maggiori di zero.')
  prepared.append((name,surname,hours,str(allocation.get('title','')).strip()))
 transferred=sum(x[2] for x in prepared)
 with db() as c:
  c.execute('begin immediate')
  source=c.execute('select * from changes where id=?',(q['id'],)).fetchone()
  if not source or source['kind']!='existing' or source['version']!=q['version']:raise ValueError('Incarico non disponibile o modificato: riaprire la pratica.')
  for i,allocation in enumerate(allocations):
   if allocation.get('teacher_id'):
    identity={};teachers.select_teacher(c,source['practice_id'],allocation['teacher_id'],identity)
    prepared[i]=(identity['NOME DOCENTE'],identity['COGNOME DOCENTE'],prepared[i][2],prepared[i][3])
  current=json.loads(source['body']);total=number(current.get('TOT ORE PREVISTE'));lectures=number(q.get('lecture_hours'))
  if lectures>total or transferred>lectures:raise ValueError('Le ore cedute non possono superare le ore di lezione e il totale dell’incarico.')
  if str(current.get('MUTUAZIONE','')).lower() in ('1','1.0','true','vero'):raise ValueError('Prima della suddivisione verificare e rimuovere la mutuazione nella proposta.')
  c.execute('insert into history(change_id,body,created) values(?,?,?)',(source['id'],json.dumps({**current,'NOTE DELLA MODIFICA':source['note']}),now()))
  current['TOT ORE PREVISTE']=round(total-transferred,10);current['OREPREVLEZ']=round(lectures-transferred,10)
  description='Redistribuzione proposta di '+str(transferred)+' ore di lezione: '+ '; '.join((name+' '+surname).strip()+': '+str(hours)+' ore' for name,surname,hours,title in prepared)+'.'
  extra=str(q.get('note','')).strip();note='\n'.join(x for x in (source['note'],description,extra) if x)
  c.execute('update changes set body=?,note=?,version=version+1 where id=?',(json.dumps(current),note,source['id']))
  for allocation,(name,surname,hours,title) in zip(allocations,prepared):
   proposed={k:current.get(k,'') for k in CONTEXT}
   proposed.update({k:0 for k in HOURS})
   proposed.update({'MUTUAZIONE':0,'PADRE MUTUAZIONE':'','CFU':'','NOME DOCENTE':name,'COGNOME DOCENTE':surname,'MATRICOLA DOCENTE':'','CF DOCENTE':'','DIPARTIMENTO AFFERENZA DOCENTE':'','ID COPERTURA':'','TITOLO AFFIDAMENTO':title,'TOT ORE PREVISTE':hours,'OREPREVLEZ':hours})
   if allocation.get('teacher_id'):teachers.select_teacher(c,source['practice_id'],allocation['teacher_id'],proposed)
   rid=c.execute('insert into records(import_id,line,body) values(NULL,0,?)',('{}',)).lastrowid
   newnote='Nuova copertura proposta per redistribuzione di ore di lezione. CFU, anagrafica e formalizzazione: [DA VERIFICARE].'
   if not title:newnote+=' Titolo affidamento: [DA VERIFICARE].'
   c.execute("insert into changes(practice_id,record_id,body,kind,source_change_id,note) values(?,?,?,'new',?,?)",(source['practice_id'],rid,json.dumps(proposed),source['id'],newnote))
 return source['practice_id']

def totals(items):
 result=[]
 for source in items:
  children=[x for x in items if x.get('source_change_id')==source['id']]
  if not children:continue
  try:
   before=number(source['before'].get('TOT ORE PREVISTE'))
   after=number(source['after'].get('TOT ORE PREVISTE'))+sum(number(x['after'].get('TOT ORE PREVISTE')) for x in children)
   delta=round(after-before,10)
   text=f"Suddivisione — {source['before'].get('MODULO','')}: {before:g} ore prima, {after:g} ore proposte. "+('Totale invariato.' if abs(delta)<1e-8 else f'Differenza {delta:+g} ore: [DA VERIFICARE].')
  except ValueError:text='Totale delle ore della suddivisione: [DA VERIFICARE], dati mancanti.'
  result.append(text)
 return result
