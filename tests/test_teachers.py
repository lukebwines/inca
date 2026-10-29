"""Only synthetic records; reference updates must never rewrite practice originals."""
import sys,sqlite3,json,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path[:0]=[str(Path(__file__).parents[1]/'inca'),str(Path(__file__).parents[1]/'inca/vendor')]
import teachers
class TeacherTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.executescript('create table imports(id integer);insert into imports values(1);create table records(import_id integer,body text);create table changes(practice_id integer,body text);')
  teachers.init(self.c)
  self.t={f:'' for f in teachers.FIELDS};self.t.update({'NOME':'Nome','COGNOME':'Prova','ORE POTENZIALE':120,'ORE CARICO PREVENTIVO':80,'ORE CARICO CONSUNTIVO':0,'id':1,'matricola':'','placeholder':False})
  self.r={'NOME DOCENTE':'Nome','COGNOME DOCENTE':'Prova','MATRICOLA DOCENTE':'000123','ANNO ACCADEMICO':'2026/2027','SATURAZIONE DOCENTE A PREVENTIVO':84}
  self.c.execute('insert into records values(1,?)',(json.dumps(self.r),));self.c.execute('insert into changes values(1,?)',(json.dumps(self.r),))
  self.upload()
 def tearDown(self):self.c.close()
 def upload(self,year='2026/2027'):
  with patch.object(teachers,'parse',return_value=[dict(self.t)]):teachers.replace(self.c,b'synthetic','synthetic.xls',year,'','TEST')
 def test_candidates_require_confirmation_and_keep_leading_zeros(self):
  r=teachers.candidates(self.c,teachers.current(self.c));self.assertEqual(r['rows'][0]['matricola'],'');self.assertEqual(r['rows'][0]['candidates'][0]['matricola'],'000123')
  teachers.link(self.c,{'report_id':r['id'],'teacher_id':1,'matricola':'000123'})
  self.assertEqual(teachers.current(self.c)['rows'][0]['matricola'],'000123')
 def test_ambiguous_and_invalid_link(self):
  self.c.execute('insert into records values(1,?)',(json.dumps(dict(self.r,**{'MATRICOLA DOCENTE':'000999'})),))
  r=teachers.candidates(self.c,teachers.current(self.c));self.assertEqual(len(r['rows'][0]['candidates']),2)
  with self.assertRaises(ValueError):teachers.link(self.c,{'report_id':r['id'],'teacher_id':1,'matricola':'INVALID'})
 def test_snapshot_survives_replacement_and_no_double_count(self):
  teachers.attach(self.c,1);snap=teachers.snapshot(self.c,1)
  self.t['ORE CARICO PREVENTIVO']=90;self.upload()
  self.assertEqual(teachers.snapshot(self.c,1),snap)
  self.assertEqual(teachers.current(self.c)['rows'][0]['ORE CARICO PREVENTIVO'],90)
  text=' '.join(teachers.summaries(snap,[{'before':self.r,'after':self.r}]))
  self.assertIn('DIFFERENZA TRA REPORT',text);self.assertIn('preventivo 80',text)
  with self.assertRaises(ValueError):teachers.attach(self.c,1)
 def test_wrong_year_and_stale_link(self):
  old=teachers.current(self.c)['id'];self.upload('2027/2028')
  with self.assertRaises(ValueError):teachers.attach(self.c,1)
  with self.assertRaises(ValueError):teachers.link(self.c,{'report_id':old,'teacher_id':1,'matricola':'000123'})
 def test_selection_and_personal_data(self):
  rid=teachers.current(self.c)['id'];teachers.link(self.c,{'report_id':rid,'teacher_id':1,'matricola':'000123'});teachers.attach(self.c,1)
  row={'CF DOCENTE':'OTHER','MATRICOLA DOCENTE':'OTHER','CFU':2}
  teachers.select_teacher(self.c,1,1,row)
  self.assertEqual(row['MATRICOLA DOCENTE'],'000123');self.assertEqual(row['CF DOCENTE'],'');self.assertEqual(row['CFU'],2)
  with self.assertRaises(ValueError):teachers.select_teacher(self.c,1,99,row)
 def test_import_validation(self):
  sheet=Mock(nrows=2);sheet.row_values.side_effect=lambda i:teachers.FIELDS if i==0 else ['Nome','Prova','SSD','SSD nuovo','Dipartimento','Qualifica',120,'80,5','']
  book=Mock();book.sheet_by_index.return_value=sheet
  with patch.object(teachers.xlrd,'open_workbook',return_value=book):
   row=teachers.parse(b'test')[0];self.assertEqual(row['ORE CARICO PREVENTIVO'],80.5);self.assertIsNone(row['ORE CARICO CONSUNTIVO'])
   sheet.nrows=3
   with self.assertRaises(ValueError):teachers.parse(b'test')
  before=teachers.current(self.c)
  with patch.object(teachers,'parse',side_effect=ValueError('bad')):
   with self.assertRaises(ValueError):teachers.replace(self.c,b'bad','bad.xls','2026/2027','','TEST')
  self.assertEqual(teachers.current(self.c),before)
if __name__=='__main__':unittest.main()
