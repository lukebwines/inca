"""Export saved proposals as native XLSX using the reference sheet's column order."""
import datetime, io, json, math, pathlib, re, zipfile
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
 def cell(row,col,value,style=0):
  ref=f'{column(col)}{row}'
  if value is None or value=='':return f'<c r="{ref}" s="{style}"/>'
  if isinstance(value,bool):return f'<c r="{ref}" s="{style}" t="b"><v>{int(value)}</v></c>'
  if isinstance(value,(int,float)) and math.isfinite(value):return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
  value=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))
  return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
 def row(n,values):cells.append(f'<row r="{n}" ht="90" customHeight="1">'+''.join(values)+'</row>')
 n=len(items);second=n+6
 for label,start,key in [('DELIBERATO',2,'before'),('PROPOSTA DI MODIFICA',second,'after')]:
  row(start,[cell(start,1,label,1)])
  row(start+1,[cell(start+1,j+1,c.get('label',c['name']),1) for j,c in enumerate(schema)])
  for i,item in enumerate(items):
   rn=start+2+i;values=[]
   for j,c in enumerate(schema):
    k=c['name'];value=item[key].get(k,'');changed=key=='after' and str(value)!=str(item['before'].get(k,''));style=2 if changed else 0
    if c.get('original_only'):
     value=item['before'].get(k,'');value='[DA VERIFICARE]' if value is None or value=='' else value;style=0
    if (k.startswith('DATA ') or k.startswith('PERIODO ')) and isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
     value=(datetime.date.fromisoformat(value)-datetime.date(1899,12,30)).days;style=4 if changed else 3
    values.append(cell(rn,j+1,value,style))
   row(rn,values)
 cols=''.join(f'<col min="{j+1}" max="{j+1}" width="{45 if c["name"] in ("CDS","INSEGNAMENTO","MODULO","PADRE MUTUAZIONE","TITOLO AFFIDAMENTO") else 20}" customWidth="1" hidden="{int(c["hidden"])}"/>' for j,c in enumerate(schema))
 sheet=f'<worksheet xmlns="{NS}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>'+''.join(cells)+'</sheetData></worksheet>'
 styles=f'''<styleSheet xmlns="{NS}"><numFmts count="1"><numFmt numFmtId="164" formatCode="dd/mm/yyyy"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFE699"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="5">'''+''.join(f'<xf numFmtId="{164 if i>=3 else 0}" fontId="{1 if i==1 else 0}" fillId="{2 if i==1 else 3 if i in (2,4) else 0}" borderId="0" xfId="0" applyAlignment="1" applyNumberFormat="1"><alignment vertical="top" wrapText="1"/></xf>' for i in range(5))+'</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'
 relns='http://schemas.openxmlformats.org/package/2006/relationships';base='http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
 files={
 '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
 '_rels/.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{base}officeDocument" Target="xl/workbook.xml"/></Relationships>',
 'xl/workbook.xml':f'<workbook xmlns="{NS}" xmlns:r="{base[:-1]}"><sheets><sheet name="Proposta di modifica" sheetId="1" r:id="rId1"/></sheets></workbook>',
 'xl/_rels/workbook.xml.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{base}worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{base}styles" Target="styles.xml"/></Relationships>',
 'xl/styles.xml':styles,'xl/worksheets/sheet1.xml':sheet}
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  for name,content in files.items():z.writestr(name,'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+content)
 return out.getvalue()
