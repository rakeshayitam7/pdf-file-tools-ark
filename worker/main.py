import base64,difflib,json,os,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from typing import Annotated
import fitz,pytesseract
from PIL import Image
from docx import Document
from openpyxl import Workbook
from fastapi import FastAPI,File,Form,Header,HTTPException,UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
app=FastAPI(title='File Tools ARK Worker',version='2.0.0')
MAX_FILE_BYTES=int(os.getenv('MAX_FILE_BYTES',str(100*1024*1024))); KEY=os.getenv('FILE_WORKER_API_KEY','')
MEDIA={'mp3-to-wav','wav-to-mp3','mp3-to-ogg','audio-compress','mp4-to-webm','webm-to-mp4','mp4-to-gif','video-compress','video-trim','video-to-mp3'}
OFFICE={'word-to-pdf','ppt-to-pdf','excel-to-pdf','pptx-to-images'}
EXTRACT={'bank-statement-tools','electricity-bill-tools','food-nutrition-files','invoice-tools'}
PDF={'split-pdf','organize-pdf','rearrange-pages','duplicate-pages','add-pages','crop-pdf','repair-pdf','flatten-pdf','optimize-pdf','linearize-pdf','protect-pdf','unlock-pdf','add-text-pdf','add-image-pdf','annotate-pdf','highlight-pdf','add-shapes-pdf','fill-pdf-forms','redact-pdf','remove-metadata','extract-images','extract-tables','compare-pdf','ai-summarize-pdf','ask-pdf'}
def run(c):
 p=subprocess.run(c,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 if p.returncode: raise RuntimeError(p.stderr[-3500:] or 'Command failed')
async def save(u,root,i):
 s=Path(u.filename or '').suffix.lower();p=root/f'in{i}{s}';n=0
 with p.open('wb') as f:
  while 1:
   b=await u.read(1024*1024)
   if not b:break
   n+=len(b)
   if n>MAX_FILE_BYTES:raise HTTPException(413,'File is too large.')
   f.write(b)
 return p
def res(p,root,m=None,n=None):return FileResponse(p,media_type=m,filename=n or p.name,headers={'Cache-Control':'no-store'},background=BackgroundTask(shutil.rmtree,root,ignore_errors=True))
def ptext(p):
 d=fitz.open(p)
 try:return '\n\n'.join(x.get_text('text') for x in d)
 finally:d.close()
def savepdf(d,p):d.save(p,garbage=4,deflate=True,clean=True)
def ocr(p):
 if p.suffix.lower()!='.pdf':
  with Image.open(p) as im:return pytesseract.image_to_string(im.convert('RGB'),config='--psm 3')
 d=fitz.open(p);a=[]
 try:
  for x in d:
   z=x.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False);a.append(pytesseract.image_to_string(Image.frombytes('RGB',[z.width,z.height],z.samples),config='--psm 3'))
  return '\n\n'.join(a)
 finally:d.close()
def fields(t):
 return {'amounts':re.findall(r'(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.\d{1,2})?)',t,re.I)[:100],'dates':re.findall(r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',t)[:100],'units':re.findall(r'\b(\d+(?:\.\d+)?)\s*(?:kWh|units?)\b',t,re.I)[:50]}
def summary(t):
 s=re.split(r'(?<=[.!?])\s+',re.sub(r'\s+',' ',t).strip())
 if len(s)<=8:return t
 return '\n'.join('• '+x for x in sorted(s,key=len,reverse=True)[:8])
def answer(t,q):
 qw=set(re.findall(r'\b[a-zA-Z0-9]{3,}\b',q.lower()));ss=[x.strip() for x in re.split(r'\n+|(?<=[.!?])\s+',t) if x.strip()]
 hits=sorted(((len(qw&set(re.findall(r'\b[a-zA-Z0-9]{3,}\b',x.lower()))),x) for x in ss),reverse=True)
 return '\n'.join(x for n,x in hits[:8] if n) or 'No matching passage was found.'
@app.get('/health')
def health():return {'ok':True,'service':'ark-file-worker','version':'2.0.0'}
@app.post('/process')
async def process(action:Annotated[str,Form()],files:Annotated[list[UploadFile],File()]=[],signature:Annotated[str|None,Form()]=None,start:Annotated[str|None,Form()]=None,duration:Annotated[str|None,Form()]=None,quality:Annotated[str|None,Form()]=None,html:Annotated[str|None,Form()]=None,options:Annotated[str|None,Form()]=None,x_ark_worker_key:Annotated[str|None,Header()]=None):
 if KEY and x_ark_worker_key!=KEY:raise HTTPException(401,'Unauthorized worker request.')
 if not files and action!='html-to-pdf':raise HTTPException(400,'At least one file is required.')
 root=Path(tempfile.mkdtemp(prefix='ark-worker-'))
 try:return await dispatch(action,[await save(f,root,i) for i,f in enumerate(files)],root,signature,start,duration,quality,html,options)
 except Exception:shutil.rmtree(root,ignore_errors=True);raise
async def dispatch(a,ins,root,signature,start,duration,quality,html,options):
 try:o=json.loads(options or '{}')
 except:o={'text':options or ''}
 if a=='ocr':
  p=root/'ocr.txt';p.write_text(ocr(ins[0]),encoding='utf8');return res(p,root,'text/plain',p.name)
 if a in {'pdf-to-jpg','pdf-to-png','pdf-to-text','pdf-to-word','compress-pdf','pdf-to-excel','pdf-to-ppt'}:
  src=ins[0]
  if a=='pdf-to-text':p=root/'document.txt';p.write_text(ptext(src),encoding='utf8');return res(p,root,'text/plain',p.name)
  if a=='pdf-to-word':
   d=fitz.open(src);w=Document();p=root/'document.docx'
   for i,x in enumerate(d):
    if i:w.add_page_break()
    for b in x.get_text('blocks'):
     if b[4].strip():w.add_paragraph(b[4].strip())
   w.save(p);d.close();return res(p,root,'application/vnd.openxmlformats-officedocument.wordprocessingml.document',p.name)
  if a in {'pdf-to-jpg','pdf-to-png'}:
   d=fitz.open(src);ext='jpg' if a.endswith('jpg') else 'png';folder=root/'pages';folder.mkdir()
   for i,x in enumerate(d):x.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(folder/f'page-{i+1}.{ext}')
   d.close();z=Path(shutil.make_archive(str(root/'pages'), 'zip',root_dir=folder));return res(z,root,'application/zip',z.name)
  if a=='pdf-to-excel':
   w=Workbook();s=w.active
   for i,x in enumerate(ptext(src).splitlines(),1):s.cell(i,1,x)
   p=root/'pdf-to-excel.xlsx';w.save(p);return res(p,root,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',p.name)
  if a=='pdf-to-ppt':
   from pptx import Presentation
   from pptx.util import Inches
   r=Presentation();r.slide_width=Inches(13.333);r.slide_height=Inches(7.5);blank=r.slide_layouts[6];d=fitz.open(src)
   for i,x in enumerate(d):
    im=root/f'slide{i}.png';x.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(im);r.slides.add_slide(blank).shapes.add_picture(str(im),0,0,width=r.slide_width,height=r.slide_height)
   p=root/'converted.pptx';r.save(p);d.close();return res(p,root,'application/vnd.openxmlformats-officedocument.presentationml.presentation',p.name)
  p=root/'compressed.pdf';run(['qpdf','--object-streams=generate','--compress-streams=y',str(src),str(p)]);return res(p,root,'application/pdf',p.name)
 if a in OFFICE:
  out=root/'office';out.mkdir();run(['libreoffice','--headless','--convert-to','pdf','--outdir',str(out),str(ins[0])]);pdf=next(out.glob('*.pdf'),None)
  if not pdf:raise RuntimeError('Office conversion failed.')
  if a=='pptx-to-images':
   d=fitz.open(pdf);folder=root/'slides';folder.mkdir()
   for i,x in enumerate(d):x.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(folder/f'slide-{i+1}.png')
   d.close();z=Path(shutil.make_archive(str(root/'slides'),'zip',root_dir=folder));return res(z,root,'application/zip','slides.zip')
  return res(pdf,root,'application/pdf','converted.pdf')
 if a=='html-to-pdf':
  if not html:raise HTTPException(400,'HTML content is required.')
  from playwright.async_api import async_playwright
  p=root/'webpage.pdf'
  async with async_playwright() as pw:
   b=await pw.chromium.launch();page=await b.new_page();await page.set_content(html,wait_until='networkidle');await page.pdf(path=str(p),format='A4',print_background=True);await b.close()
  return res(p,root,'application/pdf',p.name)
 if a in EXTRACT:
  t=ptext(ins[0]) if ins[0].suffix.lower()=='.pdf' else ins[0].read_text(encoding='utf8',errors='ignore');name=a.replace('-tools','');p=root/f'{name}.json';p.write_text(json.dumps({'tool':name,'fields':fields(t),'text':t[:200000]},ensure_ascii=False,indent=2),encoding='utf8');return res(p,root,'application/json',p.name)
 if a in MEDIA:
  src=ins[0];q=max(10,min(100,int(quality or 82)))
  mp={'mp3-to-wav':('converted.wav',['-vn','-acodec','pcm_s16le']),'wav-to-mp3':('converted.mp3',['-vn','-codec:a','libmp3lame','-b:a','192k']),'mp3-to-ogg':('converted.ogg',['-vn','-codec:a','libvorbis','-q:a','5']),'audio-compress':('compressed.mp3',['-vn','-codec:a','libmp3lame','-b:a',f'{max(64,q*2)}k']),'mp4-to-webm':('converted.webm',['-c:v','libvpx-vp9','-crf','32','-b:v','0','-c:a','libopus']),'webm-to-mp4':('converted.mp4',['-c:v','libx264','-crf','23','-c:a','aac']),'mp4-to-gif':('converted.gif',['-vf','fps=10,scale=720:-1:flags=lanczos','-an']),'video-compress':('compressed.mp4',['-c:v','libx264','-crf','30','-preset','medium','-c:a','aac','-b:a','96k']),'video-trim':('trimmed.mp4',['-ss',start or '00:00:00','-t',duration or '00:00:10','-c','copy']),'video-to-mp3':('audio.mp3',['-vn','-codec:a','libmp3lame','-b:a','192k'])}
  name,args=mp[a];p=root/name;run(['ffmpeg','-y','-i',str(src),*args,str(p)]);mime={'.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg','.mp4':'video/mp4','.webm':'video/webm','.gif':'image/gif'}.get(p.suffix,'application/octet-stream');return res(p,root,mime,p.name)
 if a in EXTRACT:raise HTTPException(422,'Extractor failed.')
 if a in PDF:
  if a=='compare-pdf':
   if len(ins)<2:raise HTTPException(400,'Upload two PDFs.')
   p=root/'comparison.txt';p.write_text('\n'.join(difflib.unified_diff(ptext(ins[0]).splitlines(),ptext(ins[1]).splitlines(),fromfile='PDF A',tofile='PDF B',lineterm='')) or 'No text differences found.',encoding='utf8');return res(p,root,'text/plain',p.name)
  if a=='extract-images':
   d=fitz.open(ins[0]);f=root/'images';f.mkdir();n=0
   for page in d:
    for im in page.get_images(full=True):
     pix=fitz.Pixmap(d,im[0]);pix=fitz.Pixmap(fitz.csRGB,pix) if pix.n-pix.alpha>3 else pix;n+=1;pix.save(f/f'image-{n}.png')
   d.close();z=Path(shutil.make_archive(str(root/'extracted-images'),'zip',root_dir=f));return res(z,root,'application/zip',z.name)
  if a=='extract-tables':
   d=fitz.open(ins[0]);w=Workbook();s=w.active;row=1
   for page in d:
    for table in page.find_tables().tables:
     for vals in table.extract():
      for col,val in enumerate(vals,1):s.cell(row,col,str(val or ''))
      row+=1
   d.close();p=root/'tables.xlsx';w.save(p);return res(p,root,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',p.name)
  if a in {'ai-summarize-pdf','ask-pdf'}:
   p=root/('summary.txt' if a.startswith('ai-') else 'answer.txt');p.write_text(summary(ptext(ins[0])) if a.startswith('ai-') else answer(ptext(ins[0]),str(o.get('question') or o.get('text') or '')),encoding='utf8');return res(p,root,'text/plain',p.name)
  if a in {'repair-pdf','optimize-pdf','linearize-pdf','protect-pdf','unlock-pdf'}:
   p=root/'processed.pdf'
   if a=='linearize-pdf':run(['qpdf','--linearize',str(ins[0]),str(p)])
   elif a=='repair-pdf':run(['qpdf','--replace-input',str(ins[0])]);shutil.copy2(ins[0],p)
   elif a=='protect-pdf':
    pw=str(o.get('password') or signature or '').strip()
    if not pw:raise HTTPException(400,'Enter a password.')
    run(['qpdf','--encrypt',pw,pw,'256','--',str(ins[0]),str(p)])
   elif a=='unlock-pdf':run(['qpdf','--password='+str(o.get('password') or signature or ''),'--decrypt',str(ins[0]),str(p)])
   else:savepdf(fitz.open(ins[0]),p)
   return res(p,root,'application/pdf',p.name)
  d=fitz.open(ins[0])
  if a in {'split-pdf','organize-pdf','rearrange-pages','duplicate-pages','add-pages'}:
   ids=list(range(len(d)))
   if a=='split-pdf':ids=ids[:1]
   if a in {'organize-pdf','rearrange-pages'} and o.get('order'):
    try:ids=[int(x)-1 for x in str(o['order']).split(',') if 0<int(x)<=len(d)]
    except:pass
   if a=='duplicate-pages' and ids:ids.append(ids[0])
   out=fitz.open()
   for i in ids:out.insert_pdf(d,from_page=i,to_page=i)
   if a=='add-pages' and len(ins)>1:out.insert_pdf(fitz.open(ins[1]))
   p=root/f'{a}.pdf';savepdf(out,p);out.close();d.close();return res(p,root,'application/pdf',p.name)
  if a=='crop-pdf':
   m=float(o.get('margin',24));
   for p in d:r=p.rect;p.set_cropbox(fitz.Rect(r.x0+m,r.y0+m,r.x1-m,r.y1-m))
  elif a=='flatten-pdf':
   for p in d:
    for w in p.widgets() or []:w.update()
  elif a=='remove-metadata':d.set_metadata({})
  elif a=='add-text-pdf':
   for p in d:p.insert_text((45,55),str(o.get('text') or signature or 'File Tools ARK'),fontsize=14)
  elif a=='add-image-pdf':
   if len(ins)<2:raise HTTPException(400,'Upload PDF and image together.')
   for p in d:p.insert_image(fitz.Rect(45,45,220,180),filename=str(ins[1]))
  elif a=='annotate-pdf':
   for p in d:p.add_text_annot((70,70),str(o.get('text') or 'Annotation'))
  elif a=='highlight-pdf':
   term=str(o.get('text') or signature or '').strip()
   if not term:raise HTTPException(400,'Enter text to highlight.')
   for p in d:
    for r in p.search_for(term):p.add_highlight_annot(r).update()
  elif a=='add-shapes-pdf':
   for p in d:p.draw_rect(fitz.Rect(45,45,220,150),color=(.2,.35,.45),width=2)
  elif a=='redact-pdf':
   term=str(o.get('text') or signature or '').strip()
   if not term:raise HTTPException(400,'Enter text to redact.')
   for p in d:
    for r in p.search_for(term):p.add_redact_annot(r,fill=(0,0,0))
    p.apply_redactions()
  elif a=='fill-pdf-forms':
   f=o.get('fields',{}) if isinstance(o.get('fields',{}),dict) else {}
   for p in d:
    for w in p.widgets() or []:
     if w.field_name in f:w.field_value=str(f[w.field_name]);w.update()
  else:raise HTTPException(422,'Worker action not implemented.')
  p=root/'processed.pdf';savepdf(d,p);d.close();return res(p,root,'application/pdf',p.name)
 if a=='zip-files':
  p=root/'files.zip'
  with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
   for i,x in enumerate(ins):z.write(x,f'file-{i+1}{x.suffix}')
  return res(p,root,'application/zip',p.name)
 if a=='unzip-files':
  f=root/'unzipped';f.mkdir();
  with zipfile.ZipFile(ins[0]) as z:z.extractall(f)
  p=Path(shutil.make_archive(str(root/'unzipped-files'),'zip',root_dir=f));return res(p,root,'application/zip',p.name)
 if a=='base64':p=root/'base64.txt';p.write_text(base64.b64encode(ins[0].read_bytes()).decode(),encoding='ascii');return res(p,root,'text/plain',p.name)
 raise HTTPException(422,f'Worker action not implemented: {a}')
