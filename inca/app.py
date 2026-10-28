import sys, pathlib, json, sqlite3, hashlib, datetime, io, secrets, os, html
from contextlib import contextmanager
from urllib.parse import urlsplit
from http.server import HTTPServer, BaseHTTPRequestHandler
sys.path.insert(0,str(pathlib.Path(__file__).parent/'vendor'))
import xlrd
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from excel_export import export_proposal
import auth
import splits
from http.cookies import SimpleCookie
import threading
ROOT=pathlib.Path(__file__).resolve().parent
INGRESS=os.environ.get('INCA_INGRESS','0')=='1'
DATA=pathlib.Path(os.environ.get('INCA_DATA', '/data' if INGRESS else str(ROOT/'dati'))); DATA.mkdir(exist_ok=True,parents=True)
TOKEN=secrets.token_urlsafe(32)
EDIT=['MUTUAZIONE','PADRE MUTUAZIONE','TAF INSEGNAMENTO','SSD INSEGNAMENTO','CFU','NOME DOCENTE','COGNOME DOCENTE','TOT ORE PREVISTE','TITOLO AFFIDAMENTO']
NUM={'CFU','MUTUAZIONE','TOT ORE PREVISTE'}
HOUR_PARTS=['OREPREVLEZ','OREPREVLAB','OREPREVESE','OREPREVSEM','OREPREVALTRO','OREPREVTIR']
def in_scope(record):
 code=str(record.get('CODICE CORSO','')).strip().upper()
 return ((len(code) in (3,4) and code.startswith('MM')) or (len(code)==4 and code.startswith('M') and code.endswith('R'))) and not any(c.isspace() for c in code)
@contextmanager
def db():
 c=sqlite3.connect(DATA/'archivio.sqlite'); c.row_factory=sqlite3.Row
 try:
  with c:yield c
 finally:c.close()
def init():
 with db() as c:
  c.executescript('CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY,name TEXT,sha TEXT UNIQUE,created TEXT); CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,import_id INTEGER,line INTEGER,body TEXT); CREATE TABLE IF NOT EXISTS practices(id INTEGER PRIMARY KEY,title TEXT,notes TEXT,created TEXT); CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY,practice_id INTEGER,record_id INTEGER,body TEXT,version INTEGER DEFAULT 1,UNIQUE(practice_id,record_id)); CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,change_id INTEGER,body TEXT,created TEXT);')
  columns={r[1] for r in c.execute('pragma table_info(changes)')}
  for name,definition in [('kind',"TEXT NOT NULL DEFAULT 'existing'"),('source_change_id','INTEGER'),('note',"TEXT NOT NULL DEFAULT ''")]:
   if name not in columns:c.execute(f'alter table changes add column {name} {definition}')
 auth.init(db)
def now():return datetime.datetime.now().isoformat(timespec='seconds')
def parse(raw):
 if not raw:raise ValueError("Nessun contenuto ricevuto. Selezionare un file XLS non vuoto e riprovare.")
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
def replace_report(payload,name):
 rows=parse(payload)
 if not rows:raise ValueError('Il report non contiene righe: archivio precedente conservato.')
 sha=hashlib.sha256(payload).hexdigest();target=None
 try:
  with db() as c:
   # Free the unique hash when the user imports the same report again.
   c.execute("update imports set sha='historical:' || id || ':' || sha where sha=?",(sha,))
   iid=c.execute('insert into imports(name,sha,created) values(?,?,?)',(name,sha,now())).lastrowid
   target=DATA/f'fonte_{iid}.xls';target.write_bytes(payload)
   c.executemany('insert into records(import_id,line,body) values(?,?,?)',[(iid,line,json.dumps(r)) for line,r in rows])
   # Existing practices own immutable original snapshots through these records.
   c.execute('delete from records where (import_id IS NULL or import_id<>?) and id not in (select record_id from changes)',(iid,))
   c.execute('delete from imports where id<>? and id not in (select import_id from records where import_id IS NOT NULL)',(iid,))
 except Exception:
  if target is not None:target.unlink(missing_ok=True)
  raise
 # Old workbooks are no longer needed; practice originals are in SQLite.
 for source in DATA.glob('fonte_*.xls'):
  if source!=target:
   try:source.unlink()
   except OSError:pass
 return len(rows)
def warnings(r):
 out=[]
 if '[DA VERIFICARE]' in str(r.get('NOTE','')):out.append(r['NOTE'])
 if r.get('ID COPERTURA','')=='':out.append('ID copertura assente: riga identificata internamente.')
 if str(r.get('COGNOME DOCENTE','')).lower()=='da definire':out.append('Docente da definire.')
 cf=str(r.get('CF DOCENTE',''))
 if cf and len(cf)!=16:out.append('Contenuto del campo CF DOCENTE da verificare.')
 parts=[r.get(k,'') for k in HOUR_PARTS]; total=r.get('TOT ORE PREVISTE','')
 if total!='' and all(v=='' or isinstance(v,(int,float)) for v in parts) and isinstance(total,(int,float)) and abs(sum(v or 0 for v in parts)-total)>0.001:out.append('Somma delle ore per tipologia diversa dal totale: verificare.')
 return out
def state():
 with db() as c:
  return {'imports':[dict(r) for r in c.execute('select * from imports order by id desc limit 1')],'practices':[dict(r) for r in c.execute('select * from practices order by id desc')],'edit':EDIT}
def practice(pid):
 with db() as c:
  p=c.execute('select * from practices where id=?',(pid,)).fetchone()
  if not p:raise ValueError('Pratica inesistente')
  items=[]
  for x in c.execute('select changes.*,records.body original from changes join records on records.id=record_id where practice_id=? order by changes.id',(pid,)):
   z=dict(x);z['before']=json.loads(z.pop('original'));z['after']=json.loads(z.pop('body'));z['warnings']=warnings(z['after']);z['history']=[dict(h) for h in c.execute('select created,body from history where change_id=? order by id desc',(z['id'],))];items.append(z)
  return {'practice':dict(p),'items':items,'hour_checks':splits.totals(items)}
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
  self.user={'id':None,'username':'Home Assistant','role':'admin'};self.csrf=TOKEN;self.external=False
  return True

 def log_message(self,*a):pass
 def send(self,data,kind='application/json',status=200):
  raw=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','same-origin');
  for key,value in getattr(self,'response_headers',[]):self.send_header(key,value)
  if getattr(self,'external',False):
   self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
  self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if not self.authorize():return
  if self.path=='/':
   base=self.headers.get('X-Ingress-Path','/') if INGRESS else '/'
   if not base.startswith('/') or base.startswith('//'):return self.send({'error':'Percorso ingress non valido'},status=400)
   base=base.rstrip('/')+'/'
   return self.send((ROOT/'index.html').read_text().replace('__TOKEN__',TOKEN).replace('__BASE__',html.escape(base,quote=True)).encode(),'text/html; charset=utf-8')
  return self.send({'error':'Non trovato'},status=404)
 def read_body(self,limit=40_000_000):
  self.connection.settimeout(60)
  transfer=self.headers.get('Transfer-Encoding','').lower().strip()
  length=self.headers.get('Content-Length')
  if transfer:
   if transfer!='chunked' or length is not None:raise ValueError('Trasferimento HTTP non valido.')
   parts=[];total=0
   while True:
    line=self.rfile.readline(8193)
    if len(line)>8192 or not line.endswith(b'\r\n'):raise ValueError('Trasferimento incompleto.')
    token=line[:-2].split(b';',1)[0]
    if not token or any(c not in b'0123456789abcdefABCDEF' for c in token):raise ValueError('Dimensione blocco non valida.')
    size=int(token,16)
    if size==0:
     trailer_size=0
     while True:
      trailer=self.rfile.readline(8193);trailer_size+=len(trailer)
      if trailer_size>8192 or not trailer.endswith(b'\r\n'):raise ValueError('Chiusura trasferimento non valida.')
      if trailer==b'\r\n':return b''.join(parts)
    total+=size
    if total>limit:raise ValueError('File troppo grande (limite 40 MB).')
    chunk=self.rfile.read(size)
    if len(chunk)!=size or self.rfile.read(2)!=b'\r\n':raise ValueError('Trasferimento incompleto.')
    parts.append(chunk)
  n=int(length or '0')
  if n<0 or n>limit:raise ValueError('File troppo grande (limite 40 MB).')
  payload=self.rfile.read(n)
  if len(payload)!=n:raise ValueError('Trasferimento incompleto.')
  return payload
 def do_POST(self):
  if not self.authorize():return
  if self.headers.get('X-Token')!=self.csrf:return self.send({'error':'Sessione non valida: riaprire la pagina'},status=403)
  try:
   if self.user['role']!='admin' and self.path in ('/import','/backup','/users','/create-user','/update-user'):return self.send({'error':'Operazione riservata agli amministratori.'},status=403)
   payload=self.read_body()
   if self.path=='/import':
    name=__import__('urllib.parse',fromlist=['unquote']).unquote(self.headers.get('X-Name','Archivio.xls'))
    return self.send({'count':replace_report(payload,name)})
   q=json.loads(payload or b'{}')
   if self.path=='/state':return self.send({**state(),'auth':{**self.user,'external':self.external}})
   if self.path=='/users':return self.send(auth.list_users(db))
   if self.path=='/create-user':
    uid=auth.create_user(db,q['username'],q['password'],q.get('role','operator'))
    return self.send({'id':uid})
   if self.path=='/update-user':
    enabled=q.get('enabled')
    if enabled is not None and not isinstance(enabled,bool):raise ValueError('Stato utente non valido.')
    auth.update_user(db,int(q['id']),enabled=enabled,password=q.get('password'))
    return self.send({'ok':True})
   if self.path=='/change-password':
    if not self.external:raise ValueError('Usare la gestione utenti da Home Assistant.')
    with db() as c:user=c.execute('select password_hash from users where id=?',(self.user['id'],)).fetchone()
    if not user or not auth.verify(q.get('current_password',''),user['password_hash']):raise ValueError('Password attuale non valida.')
    auth.update_user(db,self.user['id'],password=q['password'])
    self.response_headers=[('Set-Cookie',self.session_cookie('',0))]
    return self.send({'ok':True})
   if self.path=='/logout':
    if self.external:
     auth.logout(db,self.session_token);self.response_headers=[('Set-Cookie',self.session_cookie('',0))]
    return self.send({'ok':True})
   if self.path=='/records':
    with db() as c:rows=[{'id':r['id'],'line':r['line'],**json.loads(r['body'])} for r in c.execute('select * from records where import_id=? and import_id=(select max(id) from imports)',(q['import_id'],))]
    return self.send([r for r in rows if in_scope(r)])
   if self.path=='/export-xlsx':return self.send(export_proposal(practice(int(q['id']))),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
   if self.path=='/split':return self.send({'id':splits.redistribute(db,now,q)})
   if self.path=='/practice':return self.send(practice(int(q['id'])))
   if self.path in ('/update-practice','/delete-practice'):
    pid=int(q['id'])
    with db() as c:
     if not c.execute('select id from practices where id=?',(pid,)).fetchone():raise ValueError('Pratica inesistente')
     if self.path=='/update-practice':
      title=str(q['title']).strip()
      if not title:raise ValueError('Inserire un titolo.')
      c.execute('update practices set title=?,notes=? where id=?',(title,str(q.get('notes','')),pid))
     else:
      c.execute('delete from history where change_id in (select id from changes where practice_id=?)',(pid,))
      c.execute('delete from changes where practice_id=?',(pid,))
      c.execute('delete from practices where id=?',(pid,))
      c.execute('delete from records where import_id IS NULL and id not in (select record_id from changes)')
    return self.send({'ok':True})
   if self.path=='/create':
    title=q['title'].strip()
    if not title:raise ValueError('Inserire un titolo.')
    ids=list(dict.fromkeys(q['ids']))
    if not ids:raise ValueError('Selezionare almeno una riga.')
    with db() as c:
     pid=c.execute('insert into practices(title,notes,created) values(?,?,?)',(title,q.get('notes',''),now())).lastrowid
     for rid in ids:
      r=c.execute('select body from records where id=? and import_id=(select max(id) from imports)',(rid,)).fetchone()
      if not r:raise ValueError('Riga non trovata')
      c.execute('insert into changes(practice_id,record_id,body) values(?,?,?)',(pid,rid,r['body']))
    return self.send({'id':pid})
   if self.path=='/save':
    with db() as c:
     c.execute('begin immediate')
     row=c.execute('select * from changes where id=?',(q['id'],)).fetchone()
     if not row or row['version']!=q['version']:raise ValueError('La riga è cambiata in un’altra finestra. Riaprire la pratica.')
     r=json.loads(row['body'])
     for k,v in q['values'].items():
      if k not in EDIT:raise ValueError('Campo non modificabile')
      if k in NUM and v!='':
       v=float(str(v).replace(',','.'))
       if not __import__('math').isfinite(v) or v<0:raise ValueError('Inserire numeri non negativi.')
       if k=='MUTUAZIONE' and v not in (0,1):raise ValueError('Mutuazione deve essere 0 o 1.')
      r[k]=v
     if row['kind']=='new' and 'TOT ORE PREVISTE' in q['values']:r['OREPREVLEZ']=r.get('TOT ORE PREVISTE','')
     elif 'TOT ORE PREVISTE' in q['values'] and c.execute('select 1 from changes where source_change_id=?',(row['id'],)).fetchone():
      previous=json.loads(row['body']);lectures=splits.number(previous.get('OREPREVLEZ'))+splits.number(r.get('TOT ORE PREVISTE'))-splits.number(previous.get('TOT ORE PREVISTE'))
      if lectures<0:raise ValueError('La riduzione supera le ore di lezione residue.')
      r['OREPREVLEZ']=round(lectures,10)
     if r.get('MUTUAZIONE')==0 and r.get('PADRE MUTUAZIONE'):raise ValueError('Rimuovere il padre mutuazione nella proposta autonoma.')
     c.execute('insert into history(change_id,body,created) values(?,?,?)',(row['id'],json.dumps({**json.loads(row['body']),'NOTE DELLA MODIFICA':row['note']}),now()))
     c.execute('update changes set body=?,note=?,version=version+1 where id=?',(json.dumps(r),str(q.get('note',row['note'])),row['id']))
    return self.send({'ok':True})
   if self.path=='/backup':
    import tempfile,zipfile
    with tempfile.TemporaryDirectory() as tmp:
     dest=sqlite3.connect(str(pathlib.Path(tmp)/'archivio.sqlite'))
     with db() as c:c.backup(dest)
     dest.execute('delete from sessions');dest.commit();dest.close();out=io.BytesIO()
     with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
      z.write(pathlib.Path(tmp)/'archivio.sqlite','dati/archivio.sqlite')
      for p in DATA.glob('fonte_*.xls'):z.write(p,'dati/'+p.name)
     return self.send(out.getvalue(),'application/zip')
   raise ValueError('Operazione non disponibile')
  except Exception as e:self.send({'error':str(e)},status=400)
class PublicHandler(Handler):
 """Separate listener: HA/proxy identity headers never grant access here."""
 external=True
 def setup(self):
  super().setup();self.connection.settimeout(20)
 def public_host(self):return str(options().get('external_host','inca.archis.uk')).strip().lower()
 def valid_host(self):
  self.external=True;self.path=urlsplit(self.path).path
  if self.headers.get('Host','').lower() not in (self.public_host(),self.public_host()+':443'):
   self.send({'error':'Host non valido.'},status=403);return False
  return True
 def session_cookie(self,token,age=auth.SESSION_SECONDS):
  return f'{auth.COOKIE}={token}; Path=/; Max-Age={age}; Secure; HttpOnly; SameSite=Lax'
 def find_session(self):
  try:
   cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''));self.session_token=cookies[auth.COOKIE].value if auth.COOKIE in cookies else ''
  except Exception:self.session_token=''
  return auth.session(db,self.session_token)
 def authorize(self):
  if not self.valid_host():return False
  if self.command=='POST' and self.headers.get('Origin')!='https://'+self.public_host():
   self.send({'error':'Origine della richiesta non valida.'},status=403);return False
  session=self.find_session()
  if not session:
   self.send({'error':'Sessione scaduta o accesso richiesto. Riapri INCA ed effettua il login.'},status=401);return False
  self.csrf=session['csrf'];self.user={k:session[k] for k in ('id','username','role')}
  return True
 def do_GET(self):
  if not self.valid_host():return
  if self.path!='/':return self.send({'error':'Non trovato'},status=404)
  session=self.find_session()
  if not session:return self.send((ROOT/'login.html').read_bytes(),'text/html; charset=utf-8')
  return self.send((ROOT/'index.html').read_text().replace('__TOKEN__',session['csrf']).replace('__BASE__','/').encode(),'text/html; charset=utf-8')
 def do_POST(self):
  if not self.valid_host():return
  if self.path!='/login':return super().do_POST()
  if self.headers.get('Origin')!='https://'+self.public_host() or self.headers.get('Content-Type','').split(';')[0]!='application/json':
   return self.send({'error':'Richiesta di accesso non valida.'},status=403)
  try:
   data=json.loads(self.read_body(limit=16384))
   token,error=auth.login(db,data.get('username',''),data.get('password',''))
   if not token:return self.send({'error':error},status=429 if error.startswith('Troppi') else 401)
   self.response_headers=[('Set-Cookie',self.session_cookie(token))]
   return self.send({'ok':True})
  except (ValueError,TypeError,KeyError,AttributeError):return self.send({'error':'Richiesta di accesso non valida.'},status=400)

if __name__=='__main__':
 init()
 port=int(os.environ.get('INCA_PORT','8099'))
 server=HTTPServer(('0.0.0.0' if INGRESS else '127.0.0.1',port),Handler)
 if INGRESS and options().get('external_enabled',True):
  external=HTTPServer(('0.0.0.0',8100),PublicHandler)
  threading.Thread(target=external.serve_forever,daemon=True).start()
  print('INCA: servizio con login disponibile sulla porta interna 8100',flush=True)
 print('INCA avviato sulla porta '+str(port),flush=True)
 server.serve_forever()
