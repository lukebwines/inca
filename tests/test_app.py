"""Regression tests: only synthetic records, no real faculty data."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import zipfile

class AppTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();os.environ['INCA_DATA']=self.tmp.name
  spec=importlib.util.spec_from_file_location('inca',Path(__file__).parents[1]/'inca/app.py')
  self.app=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.app);self.app.init()
  self.server=self.app.HTTPServer(('127.0.0.1',0),self.app.Handler)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
  self.url='http://127.0.0.1:'+str(self.server.server_port)
  self.record={'CDS':'Corso sintetico','ANNO ACCADEMICO':'TEST','INSEGNAMENTO':'Attività di test','ID COPERTURA':'','MUTUAZIONE':1,'PADRE MUTUAZIONE':'Attività padre sintetica','CFU':1,'TOT ORE PREVISTE':6,'OREPREVESE':6,'NOTE':''}
  with self.app.db() as c:
   c.execute('insert into imports(name,sha,created) values(?,?,?)',('test.xls','synthetic','TEST'))
   c.execute('insert into records(import_id,line,body) values(?,?,?)',(1,2,json.dumps(self.record)))
 def tearDown(self):
  self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
 def call(self,path,data=None,token=True,headers=None):
  h={'X-Token':self.app.TOKEN} if token else {}
  h.update(headers or {})
  req=urllib.request.Request(self.url+path,data=json.dumps(data or {}).encode(),headers=h)
  with urllib.request.urlopen(req) as r:
   return r.read() if path in ('/backup','/export-xlsx') else json.load(r)
 def create(self):return self.call('/create',{'title':'Pratica sintetica','ids':[1]})['id']
 def test_roundtrip_and_conflict(self):
  pid=self.create();x=self.call('/practice',{'id':pid})['items'][0]
  self.call('/save',{'id':x['id'],'version':1,'values':{'MUTUAZIONE':'0','PADRE MUTUAZIONE':'','NOME DOCENTE':'A BANDO','TOT ORE PREVISTE':'8'}})
  saved=self.call('/practice',{'id':pid})['items'][0]
  self.assertEqual(saved['before'],self.record);self.assertEqual(saved['after']['MUTUAZIONE'],0)
  self.assertEqual(saved['after']['TOT ORE PREVISTE'],8);self.assertEqual(len(saved['history']),1)
  with self.assertRaises(urllib.error.HTTPError) as ctx:self.call('/save',{'id':x['id'],'version':1,'values':{'NOTE':'stale'}})
  self.assertEqual(ctx.exception.code,400)
  self.app.init();self.assertEqual(len(self.call('/state')['practices']),1)
 def test_validation_and_atomic_failure(self):
  pid=self.create();x=self.call('/practice',{'id':pid})['items'][0]
  for values in [{'TOT ORE PREVISTE':'-1'},{'CFU':'nan'},{'MUTUAZIONE':'0'},{'PERIODO INIZIO':'2026-12-02','PERIODO FINE':'2026-01-01'}]:
   with self.assertRaises(urllib.error.HTTPError):self.call('/save',{'id':x['id'],'version':1,'values':values})
  self.assertEqual(self.call('/practice',{'id':pid})['items'][0]['version'],1)
  with self.assertRaises(urllib.error.HTTPError):self.call('/create',{'title':'bad','ids':[1,999]})
  self.assertEqual(len(self.call('/state')['practices']),1)
 def test_excel_export(self):
  import xml.etree.ElementTree as ET
  pid=self.create();x=self.call('/practice',{'id':pid})['items'][0]
  self.call('/save',{'id':x['id'],'version':1,'values':{'MUTUAZIONE':'0','PADRE MUTUAZIONE':'','NOME DOCENTE':'=TEST()','TAF INSEGNAMENTO':'F','SSD INSEGNAMENTO':'TEST/01'}})
  raw=self.call('/export-xlsx',{'id':pid});ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   for name in z.namelist():ET.fromstring(z.read(name))
   root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
   cells={c.attrib['r']:c for c in root.findall('.//m:c',ns)}
   value=lambda ref: ''.join(cells[ref].itertext())
   self.assertEqual(value('D2'),'DELIBERATO');self.assertEqual(value('D7'),'PROPOSTA DI MODIFICA')
   self.assertEqual(value('D4'),'Corso sintetico');self.assertEqual(value('D9'),'Corso sintetico')
   self.assertEqual(value('P4'),'1');self.assertEqual(value('P9'),'0.0');self.assertEqual(cells['P9'].attrib['s'],'2')
   self.assertEqual(value('X9'),'=TEST()');self.assertEqual(cells['X9'].attrib['t'],'inlineStr');self.assertFalse(root.findall('.//m:f',ns))
   self.assertEqual(value('R9'),'F');self.assertEqual(value('T9'),'TEST/01')
  self.assertEqual(self.call('/practice',{'id':pid})['items'][0]['before'],self.record)
  with self.assertRaises(urllib.error.HTTPError):self.call('/export-xlsx',{'id':pid},token=False)
  with self.assertRaises(urllib.error.HTTPError):self.call('/export-xlsx',{'id':999})
 def test_course_scope_and_editable_fields(self):
  for code,expected in [('M123',True),('MABC',True),(' M001 ',True),('X123',False),('M1234',False),('M12',False),('',False)]:
   self.assertEqual(self.app.in_scope({'CODICE CORSO':code}),expected)
  with self.app.db() as c:
   for code in ['M001','X001','M1234']:
    c.execute('insert into records(import_id,line,body) values(?,?,?)',(1,3,json.dumps({**self.record,'CODICE CORSO':code})))
  self.assertEqual([r['CODICE CORSO'] for r in self.call('/records',{'import_id':1})],['M001'])
  pid=self.create();x=self.call('/practice',{'id':pid})['items'][0]
  self.assertEqual(len(self.call('/state')['edit']),9)
  for field in ['NOTE','MATRICOLA DOCENTE','CF DOCENTE','PERIODO INIZIO','OREPREVLEZ']:
   with self.assertRaises(urllib.error.HTTPError):self.call('/save',{'id':x['id'],'version':1,'values':{field:'test'}})
  self.call('/save',{'id':x['id'],'version':1,'values':{'TAF INSEGNAMENTO':'F','SSD INSEGNAMENTO':'TEST/01'}})
  result=self.call('/practice',{'id':pid})['items'][0]
  self.assertEqual(result['after']['TAF INSEGNAMENTO'],'F');self.assertEqual(result['before'],self.record)
 def test_backup(self):
  self.create();self.app.DATA.joinpath('fonte_1.xls').write_bytes(b'synthetic bytes')
  raw=self.call('/backup')
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   self.assertIsNone(z.testzip());self.assertEqual(z.read('dati/fonte_1.xls'),b'synthetic bytes')
   target=Path(self.tmp.name)/'restored.sqlite';target.write_bytes(z.read('dati/archivio.sqlite'))
  with sqlite3.connect(target) as c:self.assertEqual(c.execute('select count(*) from practices').fetchone()[0],1)
 def test_ingress_and_security(self):
  with self.assertRaises(urllib.error.HTTPError):self.call('/state',token=False)
  self.assertTrue(self.app.allowed_peer('172.30.32.2',True));self.assertFalse(self.app.allowed_peer('127.0.0.1',True))
  self.app.INGRESS=True
  with self.assertRaises(urllib.error.HTTPError):self.call('/state',headers={'X-Forwarded-For':'172.30.32.2','X-Remote-User-Name':'test'})
  # Simulate a proxy peer only inside this test, never via a request header.
  original=self.app.allowed_peer;self.app.allowed_peer=lambda ip,ingress: True
  with self.assertRaises(urllib.error.HTTPError):self.call('/state')
  self.app.DATA.joinpath('options.json').write_text(json.dumps({'allowed_user':'test'}))
  self.assertEqual(self.call('/state',headers={'X-Remote-User-Name':'test'})['edit'],self.app.EDIT)
  with self.assertRaises(urllib.error.HTTPError):self.call('/state',headers={'X-Remote-User-Name':'other'})
  req=urllib.request.Request(self.url+'/',headers={'X-Ingress-Path':'/api/hassio_ingress/test','X-Remote-User-Name':'test'})
  with urllib.request.urlopen(req) as r:html=r.read().decode()
  self.assertIn('<base href="/api/hassio_ingress/test/">',html)
  self.assertNotIn("fetch('/",html)
  self.app.allowed_peer=original
 def test_upload_http_framing(self):
  import http.client
  from unittest.mock import patch
  for chunked in (False,True):
   payload=b'synthetic XLS bytes '+str(chunked).encode()
   conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
   body=iter([payload[:7],payload[7:]]) if chunked else payload
   with patch.object(self.app,'parse',return_value=[(2,self.record)]) as parser:
    conn.request('POST','/import',body=body,headers={'X-Token':self.app.TOKEN},encode_chunked=chunked)
    response=conn.getresponse();result=json.loads(response.read())
    self.assertEqual(response.status,200,result);parser.assert_called_once_with(payload)
   conn.close()
  with self.app.db() as c:self.assertEqual(c.execute('select count(*) from imports').fetchone()[0],3)
 def test_empty_upload_is_actionable(self):
  with self.assertRaisesRegex(ValueError,'Nessun contenuto'):self.app.parse(b'')
  req=urllib.request.Request(self.url+'/import',data=b'',headers={'X-Token':self.app.TOKEN})
  with self.assertRaises(urllib.error.HTTPError) as ctx:urllib.request.urlopen(req)
  self.assertIn('Nessun contenuto',json.loads(ctx.exception.read())['error'])
  self.assertEqual(len(self.call('/state')['imports']),1)
 def test_xls_conversion(self):
  from unittest.mock import patch
  sheet=type('Sheet',(),{'nrows':2,'row_values':lambda _,i: ['CDS','ID COPERTURA','ANNO ACCADEMICO','INSEGNAMENTO','PERIODO INIZIO'] if i==0 else ['Test','000123','TEST','Test',46000],'cell_type':lambda _,i,j:3 if j==4 else 1})()
  book=type('Book',(),{'datemode':0,'sheet_by_index':lambda _,i:sheet})()
  with patch.object(self.app.xlrd,'open_workbook',return_value=book):rows=self.app.parse(b'synthetic')
  self.assertEqual(rows[0][1]['ID COPERTURA'],'000123');self.assertRegex(rows[0][1]['PERIODO INIZIO'],r'^\d{4}-\d{2}-\d{2}$')

if __name__=='__main__':unittest.main()
