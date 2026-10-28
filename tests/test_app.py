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
   self.assertEqual(value('A2'),'DELIBERATO');self.assertEqual(value('A7'),'PROPOSTA DI MODIFICA')
   self.assertEqual(value('A4'),'Attività di test');self.assertEqual(value('A9'),'Attività di test')
   self.assertEqual(value('K9'),'=TEST()');self.assertEqual(cells['K9'].attrib['t'],'inlineStr');self.assertFalse(root.findall('.//m:f',ns))
   self.assertEqual(value('E9'),'F');self.assertEqual(value('G9'),'TEST/01')
   expected='INSEGNAMENTO|DISCRIMINANTE DI OI|MODULO|ANNO|TAF INSEGNAMENTO|FUORI PIANO|SSD INSEGNAMENTO|CFU|MOODLE|MATRICOLA DOCENTE|NOME DOCENTE|COGNOME DOCENTE|TOT ORE PREVISTE|PERIODO INIZIO|PERIODO FINE|DIPARTIMENTO AFFERENZA DOCENTE|TITOLO AFFIDAMENTO|SATURAZIONE DOCENTE A PREVENTIVO (PREMODIFICA)'.split('|')
   self.assertEqual([value(c.attrib['r']) for c in root.find("m:sheetData/m:row[@r='3']",ns)],expected)
   self.assertEqual(len(root.find("m:sheetData/m:row[@r='9']",ns)),18)
  self.assertEqual(self.call('/practice',{'id':pid})['items'][0]['before'],self.record)
  with self.assertRaises(urllib.error.HTTPError):self.call('/export-xlsx',{'id':pid},token=False)
  with self.assertRaises(urllib.error.HTTPError):self.call('/export-xlsx',{'id':999})
 def test_original_saturation_export(self):
  import xml.etree.ElementTree as ET
  ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
  for value in (0,125.5,'',None):
   before={'SATURAZIONE DOCENTE A PREVENTIVO':value}
   raw=self.app.export_proposal({'items':[{'before':before,'after':{'SATURAZIONE DOCENTE A PREVENTIVO':999}}]})
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    root=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    for ref in ('R4','R9'):
     cell=root.find(f".//m:c[@r='{ref}']",ns)
     self.assertEqual(''.join(cell.itertext()),'[DA VERIFICARE]' if value is None or value=='' else str(value))
     self.assertEqual(cell.attrib['s'],'0')
 def test_course_scope_and_editable_fields(self):
  for code,expected in [('MM1',True),(' mma ',True),('MM',False),('M1R',False),('MM01',True),('MMAR',True),('MA1R',True),(' M00R ',True),('mm01',True),('M123',False),('MABC',False),('M001',False),('MM 1',False),('MM123',False),('X123',False),('M1234',False),('M12',False),('',False)]:
   self.assertEqual(self.app.in_scope({'CODICE CORSO':code}),expected)
  with self.app.db() as c:
   for code in ['MM1','MM01','M01R','M001','X001','M1234']:
    c.execute('insert into records(import_id,line,body) values(?,?,?)',(1,3,json.dumps({**self.record,'CODICE CORSO':code})))
  self.assertEqual([r['CODICE CORSO'] for r in self.call('/records',{'import_id':1})],['MM1','MM01','M01R'])
  pid=self.create();x=self.call('/practice',{'id':pid})['items'][0]
  self.assertEqual(len(self.call('/state')['edit']),9)
  for field in ['NOTE','MATRICOLA DOCENTE','CF DOCENTE','PERIODO INIZIO','OREPREVLEZ']:
   with self.assertRaises(urllib.error.HTTPError):self.call('/save',{'id':x['id'],'version':1,'values':{field:'test'}})
  self.call('/save',{'id':x['id'],'version':1,'values':{'TAF INSEGNAMENTO':'F','SSD INSEGNAMENTO':'TEST/01'}})
  result=self.call('/practice',{'id':pid})['items'][0]
  self.assertEqual(result['after']['TAF INSEGNAMENTO'],'F');self.assertEqual(result['before'],self.record)
 def test_replace_report_preserves_practices_and_rolls_back(self):
  from unittest.mock import patch
  pid=self.create();item=self.call('/practice',{'id':pid})['items'][0]
  self.call('/save',{'id':item['id'],'version':1,'values':{'TOT ORE PREVISTE':'8'}})
  before=self.call('/practice',{'id':pid})
  self.app.DATA.joinpath('fonte_1.xls').write_bytes(b'old')
  record={**self.record,'CODICE CORSO':'MM01','TOT ORE PREVISTE':99}
  with patch.object(self.app,'parse',return_value=[(2,record)]):
   self.app.replace_report(b'new','new.xls')
  state=self.call('/state');self.assertEqual(len(state['imports']),1);iid=state['imports'][0]['id']
  self.assertEqual(self.call('/records',{'import_id':1}),[])
  self.assertEqual(self.call('/records',{'import_id':iid})[0]['TOT ORE PREVISTE'],99)
  self.assertEqual(self.call('/practice',{'id':pid}),before)
  self.assertEqual(len(list(self.app.DATA.glob('fonte_*.xls'))),1)
  with patch.object(self.app,'parse',return_value=[]):
   with self.assertRaises(ValueError):self.app.replace_report(b'empty','empty.xls')
  with patch.object(self.app,'parse',return_value=[(2,{'bad':object()})]):
   with self.assertRaises(TypeError):self.app.replace_report(b'bad','bad.xls')
  self.assertEqual(self.call('/state'),state)
  self.assertEqual(self.app.DATA.joinpath(f'fonte_{iid}.xls').read_bytes(),b'new')
  with patch.object(self.app,'parse',return_value=[(2,record)]):self.app.replace_report(b'new','again.xls')
  self.assertEqual(self.call('/state')['imports'][0]['name'],'again.xls')
  self.assertEqual(self.call('/practice',{'id':pid}),before)
  with self.app.db() as c:self.assertEqual(c.execute('select count(*) from records').fetchone()[0],2)
 def test_manage_practices(self):
  pid=self.create();other=self.create();x=self.call('/practice',{'id':pid})['items'][0]
  self.call('/save',{'id':x['id'],'version':1,'values':{'CFU':'2'}})
  self.call('/update-practice',{'id':pid,'title':'Titolo aggiornato','notes':'Note aggiornate'})
  self.assertEqual(self.call('/practice',{'id':pid})['practice']['title'],'Titolo aggiornato')
  with self.assertRaises(urllib.error.HTTPError):self.call('/update-practice',{'id':pid,'title':' '})
  with self.assertRaises(urllib.error.HTTPError):self.call('/delete-practice',{'id':pid},token=False)
  self.call('/delete-practice',{'id':pid})
  with self.assertRaises(urllib.error.HTTPError):self.call('/practice',{'id':pid})
  self.assertEqual(self.call('/practice',{'id':other})['items'][0]['before'],self.record)
  with self.app.db() as c:
   self.assertEqual(c.execute('select count(*) from history').fetchone()[0],0)
   self.assertEqual(c.execute('select count(*) from records').fetchone()[0],1)
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
  with self.app.db() as c:self.assertEqual(c.execute('select count(*) from imports').fetchone()[0],1)
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
