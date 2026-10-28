"""Local accounts and revocable sessions. No credentials are stored in options."""
import hashlib, hmac, re, secrets, time
ITERATIONS=600_000
SESSION_SECONDS=8*60*60
COOKIE='__Host-inca_session'

def init(db):
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,csrf TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts(username TEXT NOT NULL,created REAL NOT NULL);''')

def password_hash(password):
 if not isinstance(password,str) or not 12<=len(password)<=1024:raise ValueError('La password deve contenere da 12 a 1024 caratteri.')
 salt=secrets.token_hex(16)
 digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),ITERATIONS).hex()
 return f'{ITERATIONS}${salt}${digest}'

def verify(password,encoded):
 if not isinstance(password,str) or len(password)>1024:return False
 iterations,salt,digest=encoded.split('$')
 actual=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),int(iterations)).hex()
 return hmac.compare_digest(digest,actual)

def create_user(db,username,password,role):
 username=str(username).strip().lower()
 if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,63}',username):raise ValueError('Nome utente: 3–64 lettere, numeri, punti, trattini o underscore.')
 if role not in ('admin','operator'):raise ValueError('Ruolo non valido.')
 encoded=password_hash(password)
 with db() as c:
  c.execute('begin immediate')
  if c.execute('select id from users where username=?',(username,)).fetchone():raise ValueError('Nome utente già presente.')
  if not c.execute('select 1 from users').fetchone() and role!='admin':raise ValueError('Il primo utente deve essere amministratore.')
  return c.execute('insert into users(username,password_hash,role) values(?,?,?)',(username,encoded,role)).lastrowid

def list_users(db):
 with db() as c:return [dict(r) for r in c.execute('select id,username,role,enabled from users order by username')]

def update_user(db,uid,enabled=None,password=None):
 encoded=password_hash(password) if password is not None else None
 with db() as c:
  c.execute('begin immediate')
  user=c.execute('select * from users where id=?',(uid,)).fetchone()
  if not user:raise ValueError('Utente inesistente.')
  if enabled is False and user['role']=='admin' and user['enabled'] and c.execute("select count(*) from users where role='admin' and enabled=1").fetchone()[0]<=1:raise ValueError('Non puoi disattivare l’ultimo amministratore.')
  if enabled is not None:c.execute('update users set enabled=? where id=?',(int(enabled),uid))
  if encoded:c.execute('update users set password_hash=? where id=?',(encoded,uid))
  c.execute('delete from sessions where user_id=?',(uid,))

def login(db,username,password):
 username=str(username).strip().lower()[:64];now=time.time()
 with db() as c:
  c.execute('begin immediate')
  c.execute('delete from login_attempts where created<?',(now-900,))
  attempts=c.execute('select count(*) from login_attempts where username=?',(username,)).fetchone()[0]
  total=c.execute('select count(*) from login_attempts where created>?',(now-60,)).fetchone()[0]
  if attempts>=5 or total>=30:return None,'Troppi tentativi. Riprova più tardi.'
  c.execute('insert into login_attempts values(?,?)',(username,now))
  user=c.execute('select * from users where username=?',(username,)).fetchone()
 # Use the same password derivation cost even when the account does not exist.
 dummy=f'{ITERATIONS}$00000000000000000000000000000000$'+('0'*64)
 valid=verify(password,user['password_hash'] if user else dummy)
 if not user or not valid or not user['enabled']:return None,'Credenziali non valide.'
 token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
 with db() as c:
  c.execute('begin immediate')
  # Account may have been reset/disabled while deriving the password.
  current=c.execute('select * from users where id=?',(user['id'],)).fetchone()
  if not current or not current['enabled'] or current['password_hash']!=user['password_hash']:return None,'Credenziali non valide.'
  c.execute('delete from login_attempts where username=?',(username,))
  c.execute('delete from sessions where expires<?',(now,))
  c.execute('insert into sessions values(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user['id'],csrf,now+SESSION_SECONDS))
 return token,None

def session(db,token):
 if not token or len(token)>128:return None
 with db() as c:
  row=c.execute('select users.id,username,role,csrf,expires from sessions join users on users.id=user_id where token_hash=? and enabled=1 and expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
  return dict(row) if row else None

def logout(db,token):
 with db() as c:c.execute('delete from sessions where token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
