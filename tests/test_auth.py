"""Integration tests for the separate public listener; synthetic accounts only."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import unittest

class AuthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();os.environ['INCA_DATA']=self.tmp.name
  spec=importlib.util.spec_from_file_location('inca_auth_test',Path(__file__).parents[1]/'inca/app.py')
  self.app=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.app);self.app.init()
  self.server=self.app.HTTPServer(('127.0.0.1',0),self.app.PublicHandler)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.cookie='';self.csrf=''
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def request(self,path='/',data=None,extra=None):
  conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
  headers={'Host':'inca.archis.uk','Origin':'https://inca.archis.uk','Content-Type':'application/json','Cookie':self.cookie,'X-Token':self.csrf}
  headers.update(extra or {})
  conn.request('GET' if data is None else 'POST',path,body=None if data is None else json.dumps(data),headers=headers)
  r=conn.getresponse();status=r.status;h=dict(r.getheaders());body=r.read();conn.close()
  return status,h,body
 def account(self,name='admin',role='admin'):
  return self.app.auth.create_user(self.app.db,name,'Synthetic-password-123',role)
 def login(self,name='admin',password='Synthetic-password-123'):
  status,h,body=self.request('/login',{'username':name,'password':password});self.assertEqual(status,200,body)
  self.cookie=h['Set-Cookie'].split(';')[0]
  for flag in ('Secure','HttpOnly','SameSite=Lax','Path=/'):self.assertIn(flag,h['Set-Cookie'])
  status,h,body=self.request();self.assertEqual(status,200)
  self.csrf=re.search("const TOKEN='([^']+)'",body.decode())[1]
  self.assertNotEqual(self.csrf,self.app.TOKEN)
  return self.cookie
 def test_closed_without_login_and_proxy_headers(self):
  status,h,body=self.request();self.assertEqual(status,200);self.assertIn(b'Accedi',body);self.assertNotIn(self.app.TOKEN.encode(),body)
  for endpoint in ('/state','/records','/practice','/backup','/export-xlsx','/create','/save','/import','/teachers','/import-teachers','/link-teacher','/attach-teachers','/users','/create-user','/delete-practice'):
   status,_,_=self.request(endpoint,{}, {'X-Remote-User-Name':'admin','X-Forwarded-For':'172.30.32.2','X-Token':self.app.TOKEN})
   self.assertEqual(status,401,endpoint)
  self.assertEqual(self.request('/',extra={'Host':'evil.test'})[0],403)
  self.assertEqual(self.request('/login',{'username':'admin','password':'x'}, {'Origin':'https://evil.test'})[0],403)
  self.assertEqual(self.request('/login',{}, {'Origin':''})[0],403)
 def test_sessions_csrf_roles_and_logout(self):
  self.account();self.account('operator','operator');self.login('operator')
  self.assertEqual(self.request('/state',{})[0],200)
  self.assertEqual(self.request('/state',{}, {'X-Token':self.app.TOKEN})[0],403)
  self.assertEqual(self.request('/state',{}, {'Origin':'https://evil.test'})[0],403)
  for endpoint in ('/users','/create-user','/update-user','/import','/import-teachers','/link-teacher','/backup'):self.assertEqual(self.request(endpoint,{})[0],403)
  cookie=self.cookie;self.assertEqual(self.request('/logout',{})[0],200)
  self.cookie=cookie;self.assertEqual(self.request('/state',{})[0],401)
  self.login();self.assertEqual(self.request('/users',{})[0],200)
  _,_,body=self.request('/users',{});self.assertNotIn(b'password_hash',body)
  with self.app.db() as c:c.execute('update sessions set expires=?',(time.time()-1,))
  self.assertEqual(self.request('/state',{})[0],401)
 def test_user_lifecycle_password_reset_and_persistence(self):
  admin=self.account();uid=self.account('operator','operator');self.login('operator')
  old_cookie=self.cookie;self.app.auth.update_user(self.app.db,uid,enabled=False)
  self.assertEqual(self.request('/state',{})[0],401)
  self.app.auth.update_user(self.app.db,uid,enabled=True)
  self.assertEqual(self.request('/state',{})[0],401)
  self.login('operator');self.app.auth.update_user(self.app.db,uid,password='Replacement-password-456')
  self.assertEqual(self.request('/state',{})[0],401)
  self.assertEqual(self.request('/login',{'username':'operator','password':'Synthetic-password-123'})[0],401)
  self.login('operator','Replacement-password-456')
  self.assertEqual(self.request('/change-password',{'current_password':'bad','password':'Another-password-123'})[0],400)
  self.assertEqual(self.request('/change-password',{'current_password':'Replacement-password-456','password':'Another-password-123'})[0],200)
  self.assertEqual(self.request('/state',{})[0],401)
  self.app.init();self.login('operator','Another-password-123')
  with self.assertRaises(ValueError):self.app.auth.update_user(self.app.db,admin,enabled=False)
  with self.app.db() as c:
   hashes=[r[0] for r in c.execute('select password_hash from users')]
   self.assertTrue(all('password-' not in x for x in hashes))
 def test_admin_api_and_shared_practices(self):
  self.account();self.login()
  status,_,body=self.request('/create-user',{'username':'worker','password':'Synthetic-password-123','role':'operator'})
  self.assertEqual(status,200,body);uid=json.loads(body)['id']
  with self.app.db() as c:
   c.execute('insert into imports(name,sha,created) values(?,?,?)',('synthetic.xls','test','TEST'))
   c.execute('insert into records(import_id,line,body) values(?,?,?)',(1,2,json.dumps({'CODICE CORSO':'M001','CFU':1})))
  self.login('worker')
  status,_,body=self.request('/create',{'title':'Shared synthetic practice','ids':[1]});self.assertEqual(status,200,body)
  pid=json.loads(body)['id'];status,_,body=self.request('/practice',{'id':pid});item=json.loads(body)['items'][0]
  self.assertEqual(self.request('/save',{'id':item['id'],'version':1,'values':{'CFU':'2'}})[0],200)
  self.login();status,_,body=self.request('/practice',{'id':pid});self.assertEqual(json.loads(body)['items'][0]['after']['CFU'],2)
  status,_,body=self.request('/update-user',{'id':uid,'enabled':False});self.assertEqual(status,200,body)
  status,_,body=self.request('/backup',{});self.assertEqual(status,200)
  import io,zipfile,sqlite3
  with zipfile.ZipFile(io.BytesIO(body)) as z:
   backup=Path(self.tmp.name)/'backup.sqlite';backup.write_bytes(z.read('dati/archivio.sqlite'))
  with sqlite3.connect(backup) as c:
   self.assertEqual(c.execute('select count(*) from sessions').fetchone()[0],0)
   self.assertEqual(c.execute('select count(*) from users').fetchone()[0],2)
 def test_no_public_bootstrap_and_rate_limits(self):
  self.assertEqual(self.request('/create-user',{'username':'hacker','password':'Synthetic-password-123','role':'admin'})[0],401)
  with self.assertRaises(ValueError):self.account('operator','operator')
  self.account()
  for _ in range(5):self.assertEqual(self.request('/login',{'username':'admin','password':'bad'})[0],401)
  self.assertEqual(self.request('/login',{'username':'admin','password':'Synthetic-password-123'})[0],429)
  with self.assertRaises(ValueError):self.app.auth.create_user(self.app.db,'bad','short','admin')
  with self.assertRaises(ValueError):self.app.auth.create_user(self.app.db,'<script>','Synthetic-password-123','admin')

if __name__=='__main__':unittest.main()
