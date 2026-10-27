import sys, pathlib, json, sqlite3, hashlib, datetime, io, secrets, os, html
from contextlib import contextmanager
from urllib.parse import urlsplit
from http.server import HTTPServer, BaseHTTPRequestHandler
sys.path.insert(0,str(pathlib.Path(__file__).parent/'vendor'))
import xlrd
ROOT=pathlib.Path(__file__).resolve().parent
INGRESS=os.environ.get('INCA_INGRESS','0')=='1'
DATA=pathlib.Path(os.environ.get('INCA_DATA', '/data' if INGRESS else str(ROOT/'dati'))); DATA.mkdir(exist_ok=True,parents=True)
TOKEN=secrets.token_urlsafe(32)
EDIT=['NOME DOCENTE','COGNOME DOCENTE','MATRICOLA DOCENTE','CF DOCENTE','DIPARTIMENTO AFFERENZA DOCENTE','CFU','OREPREVLEZ','OREPREVLAB','OREPREVESE','OREPREVSEM','OREPREVALTRO','OREPREVTIR','TOT ORE PREVISTE','TITOLO AFFIDAMENTO','MUTUAZIONE','PADRE MUTUAZIONE','PERIODO INIZIO','PERIODO FINE','NOTE']
NUM={'CFU','MUTUAZIONE',*[k for k in EDIT if k.startswith('OREPREV')],'TOT ORE PREVISTE'}
@contextmanager
def db():
 c=sqlite3.connect(DATA/'archivio.sqlite'); c.row_factory=sqlite3.Row
 try:
  with c:yield c
 finally:c.close()
def init():
 with db() as c:
  c.executescript('CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,name TEXT,sha TEXT UNIQUE,created TEXT); CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,import_id INTEGER,line INTEGER,body TEXT); CREATE TABLE IF NOT EXISTS practices(id INTEGER PRIMARY KEY,title TEXT,notes TEXT,created TEXT); CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY,practice_id INTEGER,record_id INTEGER,body TEXT,version INTEGER DEFAULT 1,UNIQUE(practice_id,record_id)); CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,change_id INTEGER,body TEXT,created TEXT);')
def now():return datetime.datetime.now().isoformat(timespec='seconds')
def parse(raw):
 b=xlrd.open_workbook(file_contents=raw,logfile=io.StringIO()); s=b.sheet_by_index(0); headers=[str(v).strip() for v in s.row_values(0)]
 if not {'CDS','ID COPERTURA','ANNO ACCADEMICO','INSEGNAMENTO'}.issubset(headers):raise ValueError('Il primo foglio non contiene le intestazioni attese.')
 result=[]
 for i in range(1,s.nrows):
  vals=s.row_values(i)
  if not any(v!='' for v in vals):continue
  for j,v in enumerate(vals):
   if s.cell_type(i,j)==xlrd.XL_CELL_DATE: vals[j]=xlrd.xldate_as_datetime(v,b.datemode).date().isoformat()
  result.append((i+1,dict(zip(headers,vals))))
 return result
def warnings(r):
 out=[]
 if '[DA VERIFICARE]' in str(r.get('NOTE','')):out.append(r['NOTE'])
 if r.get('ID COPERTURA','')=='':out.append('ID copertura assente: riga identificata internamente.')
 if str(r.get('COGNOME DOCENTE','')).lower()=='da definire':out.append('Docente da definire.')
 cf=str(r.get('CF DOCENTE',''))
 if cf and len(cf)!=16:out.append('Contenuto del campo CF DOCENTE da verificare.')
 parts=[r.get(k,'') for k in EDIT if k.startswith('OREPREV')]; total=r.get('TOT ORE PREVISTE','')
 if total!='' and all(v=='' or isinstance(v,(int,float)) for v in parts) and isinstance(total,(int,float)) and abs(sum(v or 0 for v in parts)-total)>0.001:out.append('Somma delle ore per tipologia diversa dal totale: verificare.')
 return out
def state():
 with db() as c:
  return {'imports':[dict(r) for r in c.execute('select * from imports order by id desc')],'practices':[dict(r) for r in c.execute('select * from practices order by id desc')],'edit':EDIT}
def practice(pid):
 with db() as c:
  p=c.execute('select * from practices where id=?',(pid,)).fetchone()
  if not p:raise ValueError('Pratica inesistente')
  items=[]
  for x in c.execute('select changes.*,records.body original from changes join records on records.id=record_id where practice_id=?',(pid,)):
   z=dict(x);z['before']=json.loads(z.pop('original'));z['after']=json.loads(z.pop('body'));z['warnings']=warnings(z['after']);z['history']=[dict(h) for h in c.execute('select created,body from history where change_id=? order by id desc',(z['id'],))];items.append(z)
  return {'practice':dict(p),'items':items}
def options():
 try:return json.loads((DATA/'options.json').read_text())
 except FileNotFoundError:return {}
def allowed_peer(ip, ingress):
 return ip=='172.30.32.2' if ingress else ip in ('127.0.0.1','::1')
class Handler(BaseHTTPRequestHandler):
 def authorize(self):
  if not allowed_peer(self.client_address[0],INGRESS):
   self.send({'error':'Accesso consentito solo tramite Home Assistant.'},status=403);return False
  if INGRESS:
   user=str(options().get('allowed_user','')).strip()
   if not user or self.headers.get('X-Remote-User-Name')!=user:
    self.send({'error':'Configurare allowed_user nelle opzioni INCA con il nome utente Home Assistant autorizzato (non il nome visualizzato).'},status=403);return False
  elif self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
   self.send({'error':'Host non valido'},status=403);return False
  self.path=urlsplit(self.path).path
  return True

 def log_message(self,*a):pass
 def send(self,data,kind='application/json',status=200):
  raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if not self.authorize():return
  if self.path=='/':
   base=self.headers.get('X-Ingress-Path','/') if INGRESS else '/'
   if not base.startswith('/') or base.startswith('//'):return self.send({'error':'Percorso ingress non valido'},status=400)
   base=base.rstrip('/')+'/'
   return self.send((ROOT/'index.html').read_text().replace('__TOKEN__',TOKEN).replace('__BASE__',html.escape(base,quote=True)).encode(),'text/html; charset=utf-8')
  return self.send({'error':'Non trovato'},status=404)
 def do_POST(self):
  if not self.authorize():return
  if self.headers.get('X-Token')!=TOKEN:return self.send({'error':'Sessione non valida: riaprire la pagina'},status=403)
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n<0 or n>40_000_000:raise ValueError('File troppo grande (limite 40 MB).')
   payload=self.rfile.read(n)
   if self.path=='/import':
    rows=parse(payload);sha=hashlib.sha256(payload).hexdigest()
    with db() as c:
     if c.execute('select id from imports where sha=?',(sha,)).fetchone():raise ValueError('Questo file è già stato importato.')
     iid=c.execute('insert into imports(name,sha,created) values(?,?,?)',(__import__('urllib.parse',fromlist=['unquote']).unquote(self.headers.get('X-Name','Archivio.xls')),sha,now())).lastrowid
     (DATA/f'fonte_{iid}.xls').write_bytes(payload)
     c.executemany('insert into records(import_id,line,body) values(?,?,?)',[(iid,line,json.dumps(r)) for line,r in rows])
    return self.send({'count':len(rows)})
   q=json.loads(payload or b'{}')
   if self.path=='/state':return self.send(state())
   if self.path=='/records':
    with db() as c:rows=[{'id':r['id'],'line':r['line'],**json.loads(r['body'])} for r in c.execute('select * from records where import_id=?',(q['import_id'],))]
    return self.send(rows)
   if self.path=='/practice':return self.send(practice(int(q['id'])))
   if self.path=='/create':
    title=q['title'].strip()
    if not title:raise ValueError('Inserire un titolo.')
    ids=list(dict.fromkeys(q['ids']))
    if not ids:raise ValueError('Selezionare almeno una riga.')
    with db() as c:
     pid=c.execute('insert into practices(title,notes,created) values(?,?,?)',(title,q.get('notes',''),now())).lastrowid
     for rid in ids:
      r=c.execute('select body from records where id=?',(rid,)).fetchone()
      if not r:raise ValueError('Riga non trovata')
      c.execute('insert into changes(practice_id,record_id,body) values(?,?,?)',(pid,rid,r['body']))
    return self.send({'id':pid})
   if self.path=='/save':
    with db() as c:
     row=c.execute('select * from changes where id=?',(q['id'],)).fetchone()
     if not row or row['version']!=q['version']:raise ValueError('La riga è cambiata in un’altra finestra. Riaprire la pratica.')
     r=json.loads(row['body'])
     for k,v in q['values'].items():
      if k not in EDIT:raise ValueError('Campo non modificabile')
      if k in NUM and v!='':
       v=float(str(v).replace(',','.'))
       if not __import__('math').isfinite(v) or v<0:raise ValueError('Inserire numeri non negativi.')
       if k=='MUTUAZIONE' and v not in (0,1):raise ValueError('Mutuazione deve essere 0 o 1.')
      if k in ['PERIODO INIZIO','PERIODO FINE'] and v:datetime.date.fromisoformat(v)
      r[k]=v
     if r.get('PERIODO INIZIO') and r.get('PERIODO FINE') and r['PERIODO INIZIO']>r['PERIODO FINE']:raise ValueError('La data finale precede quella iniziale.')
     if r.get('MUTUAZIONE')==0 and r.get('PADRE MUTUAZIONE'):raise ValueError('Rimuovere il padre mutuazione nella proposta autonoma.')
     c.execute('insert into history(change_id,body,created) values(?,?,?)',(row['id'],row['body'],now()))
     c.execute('update changes set body=?,version=version+1 where id=?',(json.dumps(r),row['id']))
    return self.send({'ok':True})
   if self.path=='/backup':
    import tempfile,zipfile
    with tempfile.TemporaryDirectory() as tmp:
     dest=sqlite3.connect(str(pathlib.Path(tmp)/'archivio.sqlite'))
     with db() as c:c.backup(dest)
     dest.close();out=io.BytesIO()
     with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
      z.write(pathlib.Path(tmp)/'archivio.sqlite','dati/archivio.sqlite')
      for p in DATA.glob('fonte_*.xls'):z.write(p,'dati/'+p.name)
     return self.send(out.getvalue(),'application/zip')
   raise ValueError('Operazione non disponibile')
  except Exception as e:self.send({'error':str(e)},status=400)
if __name__=='__main__':
 init()
 port=int(os.environ.get('INCA_PORT','8099'))
 server=HTTPServer(('0.0.0.0' if INGRESS else '127.0.0.1',port),Handler)
 print('INCA avviato sulla porta '+str(port),flush=True)
 server.serve_forever()
