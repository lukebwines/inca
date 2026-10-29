"""Export saved proposals as native XLSX using the reference sheet's column order."""
import datetime, io, json, math, pathlib, re, textwrap, zipfile
from xml.sax.saxutils import escape

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def column(n):
 result=''
 while n:
  n,k=divmod(n-1,26);result=chr(65+k)+result
 return result

def export_proposal(practice):
 schema=json.loads(pathlib.Path(__file__).with_name('export_schema.json').read_text())
 items=practice['items']
 cells=[]
 widths={'CDS':38,'ANNO ACCADEMICO':14,'INSEGNAMENTO':34,'DISCRIMINANTE DI OI':18,'MODULO':34,'ANNO':8,'TAF INSEGNAMENTO':18,'FUORI PIANO':12,'SSD INSEGNAMENTO':16,'CFU':16,'MOODLE':10,'MATRICOLA DOCENTE':18,'NOME DOCENTE':22,'COGNOME DOCENTE':22,'TOT ORE PREVISTE':14,'PERIODO INIZIO':15,'PERIODO FINE':15,'DIPARTIMENTO AFFERENZA DOCENTE':28,'TITOLO AFFIDAMENTO':36,'SATURAZIONE DOCENTE A PREVENTIVO':25,'NOTE DELLA MODIFICA':64}
 last=column(len(schema));merged=[]
 def height(values):
  lines=1
  for c,v in zip(schema,values):
   if c.get('hidden'):continue
   width=max(8,int(widths.get(c['name'],20)*.9))
   count=sum(max(1,len(textwrap.wrap(line,width=width))) for line in str(v).split('\n'))
   lines=max(lines,count)
  return min(409,max(42,lines*15+12))

 def cell(row,col,value,style=0):
  ref=f'{column(col)}{row}'
  if value is None or value=='':return f'<c r="{ref}" s="{style}"/>'
  if isinstance(value,bool):return f'<c r="{ref}" s="{style}" t="b"><v>{int(value)}</v></c>'
  if isinstance(value,(int,float)) and math.isfinite(value):return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
  value=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))
  return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
 def row(n,values,ht=28):cells.append(f'<row r="{n}" ht="{ht}" customHeight="1">'+''.join(values)+'</row>')
 title=practice.get('practice',{}).get('title','Proposta di modifica')
 row(1,[cell(1,1,'INCA · '+title,6)],32)
 merged.append(f'<mergeCell ref="A1:{last}1"/>')
 originals=[x for x in items if x.get('kind')!='new']
 n=len(originals);second=n+6
 for label,start,key in [('DELIBERATO',2,'before'),('PROPOSTA DI MODIFICA',second,'after')]:
  row(start,[cell(start,j+1,label if j==0 else "",5) for j in range(len(schema))],28)
  merged.append(f'<mergeCell ref="A{start}:{last}{start}"/>')
  row(start+1,[cell(start+1,j+1,c.get('label',c['name']),1) for j,c in enumerate(schema)],66)
  for i,item in enumerate(originals if key=='before' else items):
   rn=start+2+i;values=[];display=[]
   for j,c in enumerate(schema):
    k=c['name'];value=item[key].get(k,'');changed=key=='after' and str(value)!=str(item['before'].get(k,''));style=7 if item.get('kind')=='new' else 2 if changed else 8 if i%2 else 0
    if c.get('item_note'):
     value=item.get('note','') if key=='after' else '';style=7 if item.get('kind')=='new' else 2 if value else 8 if i%2 else 0
    if item.get('kind')=='new' and value in ('',None) and k in ('CFU','NOME DOCENTE','COGNOME DOCENTE','TITOLO AFFIDAMENTO','MATRICOLA DOCENTE','DIPARTIMENTO AFFERENZA DOCENTE'):value='[DA VERIFICARE]'
    if c.get('original_only'):
     value=item['before'].get(k,'');value='[DA VERIFICARE]' if value is None or value=='' else value;style=7 if item.get('kind')=='new' else 8 if i%2 else 0
    if value=='[DA VERIFICARE]':style=9
    display.append(value)
    if (k.startswith('DATA ') or k.startswith('PERIODO ')) and isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
     value=(datetime.date.fromisoformat(value)-datetime.date(1899,12,30)).days;style={0:3,2:4,7:10,8:11}.get(style,3)
    values.append(cell(rn,j+1,value,style))
   row(rn,values,height(display))
 footer=second+len(items)+3
 notes=['Legenda: ambra = dato modificato · verde chiaro = nuova copertura proposta · rosso chiaro = dato da verificare',practice.get('practice',{}).get('notes','')]+practice.get('hour_checks',[])+practice.get('teacher_summary',[])
 for note in notes:
  if note:
   row(footer,[cell(footer,1,note,12)],max(30,15*(1+len(note)//180)));merged.append(f'<mergeCell ref="A{footer}:{column(len(schema))}{footer}"/>');footer+=1
 cols=''.join(f'<col min="{j+1}" max="{j+1}" width="{widths.get(c["name"],20)}" customWidth="1" hidden="{int(c["hidden"])}"/>' for j,c in enumerate(schema))
 sheet=f'<worksheet xmlns="{NS}"><sheetPr><tabColor rgb="FF17394C"/></sheetPr><dimension ref="A1:{last}{footer-1}"/><sheetViews><sheetView workbookViewId="0" showGridLines="0" zoomScale="85"><pane xSplit="2" ySplit="3" topLeftCell="C4" activePane="bottomRight" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="18"/><cols>{cols}</cols><sheetData>'+''.join(cells)+'</sheetData><mergeCells count="'+str(len(merged))+'">'+''.join(merged)+'</mergeCells><printOptions horizontalCentered="1"/><pageMargins left="0.25" right="0.25" top="0.4" bottom="0.4" header="0.2" footer="0.2"/><pageSetup paperSize="8" orientation="landscape" scale="80" pageOrder="overThenDown"/><headerFooter><oddFooter>&amp;LINCA · Affidamenti didattici&amp;RPagina &amp;P di &amp;N</oddFooter></headerFooter></worksheet>'
 fonts=[(10,'243746',False),(10,'FFFFFF',True),(14,'17394C',True),(10,'9C2F25',True),(10,'526575',False)]
 fontxml=''.join(f'<font>{"<b/>" if bold else ""}<sz val="{size}"/><color rgb="FF{color}"/><name val="Calibri"/></font>' for size,color,bold in fonts)
 fills=['17394C','FFF0C2','E8F3ED','F4F7FA','FCE8E6','E7EEF3']
 fillxml='<fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'+''.join(f'<fill><patternFill patternType="solid"><fgColor rgb="FF{c}"/><bgColor indexed="64"/></patternFill></fill>' for c in fills)
 # font, fill, number format, border: existing cell style IDs remain stable.
 specs=[(0,0,0,1),(1,2,0,2),(0,3,0,1),(0,0,164,1),(0,3,164,1),(1,2,0,0),(2,0,0,0),(0,4,0,1),(0,5,0,1),(3,6,0,1),(0,4,164,1),(0,5,164,1),(4,7,0,0)]
 xfs=''
 for i,(font,fill,num,border) in enumerate(specs):
  vertical='center' if i in (1,5,6) else 'top'
  horizontal=' horizontal="center"' if i==1 else ''
  xfs+=f'<xf numFmtId="{num}" fontId="{font}" fillId="{fill}" borderId="{border}" xfId="0" applyAlignment="1" applyNumberFormat="1"><alignment vertical="{vertical}"{horizontal} wrapText="1"/></xf>'
 styles=f'<styleSheet xmlns="{NS}"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts><fonts count="{len(fonts)}">{fontxml}</fonts><fills count="8">{fillxml}</fills><borders count="3"><border/><border><bottom style="hair"><color rgb="FFD8E2E8"/></bottom></border><border><right style="thin"><color rgb="FFFFFFFF"/></right></border></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="{len(specs)}">{xfs}</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
 relns='http://schemas.openxmlformats.org/package/2006/relationships';base='http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
 files={
 '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
 '_rels/.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{base}officeDocument" Target="xl/workbook.xml"/></Relationships>',
 'xl/workbook.xml':f'<workbook xmlns="{NS}" xmlns:r="{base[:-1]}"><sheets><sheet name="Proposta di modifica" sheetId="1" r:id="rId1"/></sheets><definedNames><definedName name="_xlnm.Print_Area" localSheetId="0">&apos;Proposta di modifica&apos;!$A$1:${last}${footer-1}</definedName><definedName name="_xlnm.Print_Titles" localSheetId="0">&apos;Proposta di modifica&apos;!$A:$B</definedName></definedNames></workbook>',
 'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{base}worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{base}styles" Target="styles.xml"/></Relationships>',
 'xl/styles.xml':styles,'xl/worksheets/sheet1.xml':sheet}
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,content in files.items():z.writestr(name,'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+content)
 return out.getvalue()
