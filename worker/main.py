import base64,csv,difflib,json,os,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from typing import Annotated
from io import BytesIO
import fitz,pytesseract
from PIL import Image
from docx import Document
from openpyxl import Workbook
from fastapi import FastAPI,File,Form,Header,HTTPException,UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
app=FastAPI(title='File Tools ARK Worker',version='2.3.0')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
MAX_FILE_BYTES=int(os.getenv('MAX_FILE_BYTES',str(500*1024*1024))); PROCESS_TIMEOUT=int(os.getenv('PROCESS_TIMEOUT_SECONDS','5400')); KEY=os.getenv('FILE_WORKER_API_KEY','')
IMAGE={'compress','resize','crop','jpg'}
MEDIA={'mp3-to-wav','wav-to-mp3','mp3-to-ogg','audio-compress','audio-cut','audio-merge','audio-speed','audio-volume','audio-reverse','audio-loop','mp4-to-webm','webm-to-mp4','mp4-to-gif','video-compress','video-trim','video-merge','video-speed','video-mute','video-resize','video-crop','video-to-mp3'}
OFFICE={'word-to-pdf','ppt-to-pdf','excel-to-pdf','pptx-to-images'}
EXTRACT={'bank-statement-tools','electricity-bill-tools','food-nutrition-files','invoice-tools'}
PDF={'merge-pdf','rotate-pdf','page-numbers','watermark','sign-pdf','metadata','split-pdf','delete-pages','draw-pdf','organize-pdf','rearrange-pages','duplicate-pages','add-pages','crop-pdf','repair-pdf','flatten-pdf','optimize-pdf','linearize-pdf','protect-pdf','unlock-pdf','add-text-pdf','add-image-pdf','annotate-pdf','highlight-pdf','add-shapes-pdf','fill-pdf-forms','redact-pdf','remove-metadata','extract-images','extract-tables','compare-pdf','ai-summarize-pdf','ask-pdf'}
def run(c):
 p=subprocess.run(c,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=PROCESS_TIMEOUT)
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
@app.head('/')
@app.head('/health')
@app.get('/')
@app.get('/health')
def health():return {'ok':True,'service':'ark-file-worker','version':'2.2.0','max_file_bytes':MAX_FILE_BYTES,'timeout_seconds':PROCESS_TIMEOUT}
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
 if a in IMAGE:
  if not ins: raise HTTPException(400,'Choose an image.')
  try:q=max(1,min(100,int(quality or o.get('quality') or 82)))
  except:q=82
  try:
   image=Image.open(ins[0])
   if a=='resize':
    width=int(o.get('width') or 0);height=int(o.get('height') or 0)
    if not width and not height:raise HTTPException(400,'Enter width or height.')
    image.thumbnail((width or image.width,height or image.height),Image.Resampling.LANCZOS)
   elif a=='crop':
    width=int(o.get('width') or 0);height=int(o.get('height') or 0);left=max(0,int(o.get('left') or 0));top=max(0,int(o.get('top') or 0))
    if not width or not height:raise HTTPException(400,'Enter crop width and height.')
    if left+width>image.width or top+height>image.height:raise HTTPException(400,'Crop area is outside the image.')
    image=image.crop((left,top,left+width,top+height))
   fmt=str(o.get('format') or 'jpg').lower();fmt=fmt if fmt in {'jpg','png','webp'} else 'jpg';out=root/('converted.'+fmt if a=='jpg' else 'processed.webp')
   if image.mode not in ('RGB','L'):image=image.convert('RGB')
   if a=='jpg':image.save(out,'JPEG',quality=q,optimize=True,progressive=True);mime='image/jpeg'
   elif fmt=='png':image.save(out,'PNG',optimize=True);mime='image/png'
   else:image.save(out,'WEBP',quality=q,method=4);mime='image/webp'
   return res(out,root,mime,out.name)
  except HTTPException:raise
  except Exception as e:raise HTTPException(400,f'Image processing failed: {e}')
 if a=='merge-pdf':
  out=fitz.open()
  for src in ins:
   if src.suffix.lower()!='.pdf':raise HTTPException(400,'Merge accepts PDF files only.')
   d=fitz.open(src);out.insert_pdf(d);d.close()
  p=root/'merged.pdf';savepdf(out,p);out.close();return res(p,root,'application/pdf',p.name)
 if a in {'jpg-to-pdf','png-to-pdf'}:
  out=fitz.open();expected='.jpg' if a=='jpg-to-pdf' else '.png'
  for src in ins:
   if src.suffix.lower() not in ({'.jpg','.jpeg'} if expected=='.jpg' else {'.png'}):raise HTTPException(400,f'Unsupported image for {a}.')
   im=Image.open(src).convert('RGB');bio=BytesIO();im.save(bio,'JPEG' if expected=='.jpg' else 'PNG');pix=fitz.Pixmap(fitz.csRGB,bio.getvalue());page=out.new_page(width=pix.width,height=pix.height);page.insert_image(page.rect,pixmap=pix)
  p=root/('images-from-jpg.pdf' if a=='jpg-to-pdf' else 'images-from-png.pdf');savepdf(out,p);out.close();return res(p,root,'application/pdf',p.name)
 if a=='txt-to-pdf':
  text=ins[0].read_text(encoding='utf8',errors='replace');out=fitz.open();font=fitz.Font('helv');margin=45;size=10;line_h=14;page=out.new_page();y=page.rect.height-margin
  for line in text.replace('\\r','').split('\\n'):
   chunks=[line[i:i+105] for i in range(0,max(len(line),1),105)] or ['']
   for chunk in chunks:
    if y<margin:page=out.new_page();y=page.rect.height-margin
    page.insert_text((margin,y),chunk,fontname='helv',fontsize=size);y-=line_h
  p=root/'text-document.pdf';savepdf(out,p);out.close();return res(p,root,'application/pdf',p.name)
 if a=='docx-to-txt':
  d=Document(str(ins[0]));p=root/'document.txt';p.write_text('\\n'.join(x.text for x in d.paragraphs),encoding='utf8');return res(p,root,'text/plain',p.name)
 if a=='csv-to-xlsx':
  out=Workbook();s=out.active
  with ins[0].open(newline='',encoding='utf8-sig',errors='replace') as f:
   for r,row in enumerate(csv.reader(f),1):
    for c,val in enumerate(row,1):s.cell(r,c,val)
  p=root/'converted.xlsx';out.save(p);return res(p,root,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',p.name)
 if a=='xlsx-to-csv':
  from openpyxl import load_workbook
  wb=load_workbook(ins[0],read_only=True,data_only=True);ws=wb.active;p=root/'converted.csv'
  with p.open('w',newline='',encoding='utf8') as f:
   cw=csv.writer(f);cw.writerows(ws.iter_rows(values_only=True))
  wb.close();return res(p,root,'text/csv',p.name)
 if a=='ocr':
  if ins[0].suffix.lower()=='.pdf':
   src=fitz.open(ins[0]);out=fitz.open()
   try:
    for page in src:
     pix=page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False);pdf=fitz.open('pdf',pix.pdfocr_tobytes(language='eng'));out.insert_pdf(pdf);pdf.close()
    p=root/'ocr-searchable.pdf';savepdf(out,p);return res(p,root,'application/pdf',p.name)
   finally:src.close();out.close()
  pix=fitz.Pixmap(str(ins[0]));
  if pix.alpha:pix=fitz.Pixmap(pix,0)
  p=root/'ocr-searchable.pdf';p.write_bytes(pix.pdfocr_tobytes(language='eng'));return res(p,root,'application/pdf',p.name)
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
 if a in {'word-to-pdf','ppt-to-pdf','excel-to-pdf','pptx-to-images'}:
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
  src=ins[0] if ins else None
  try:q=max(10,min(100,int(quality or 82)))
  except:q=82
  if not src:raise HTTPException(400,'Choose a media file.')
  if a=='audio-merge':
   if len(ins)<2:raise HTTPException(400,'Choose at least two audio files.')
   listfile=root/'concat.txt'
   with listfile.open('w',encoding='utf8') as f:
    for x in ins:f.write("file "+str(x).replace("'","'\\''")+"\\n")
   p=root/'merged.mp3';run(['ffmpeg','-y',*[x for pair in [['-i',str(src)] for src in ins] for x in pair],'-filter_complex',f'concat=n={len(ins)}:v=0:a=1','-c:a','libmp3lame','-b:a','192k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='audio-cut':
   p=root/'cut.mp3';run(['ffmpeg','-y','-ss',start or '00:00:00','-i',str(src),'-t',duration or '00:00:10' ,'-vn','-c:a','libmp3lame','-b:a','192k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='audio-speed':
   speed=max(.25,min(4.0,float(o.get('speed') or 1.0)))
   filters=[]
   remain=speed
   while remain>2:filters.append('atempo=2');remain/=2
   while remain<0.5:filters.append('atempo=0.5');remain/=0.5
   filters.append(f'atempo={remain:.4f}')
   p=root/'speed-changed.mp3';run(['ffmpeg','-y','-i',str(src),'-vn','-af',','.join(filters),'-c:a','libmp3lame','-b:a','192k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='audio-volume':
   volume=max(.1,min(4.0,float(o.get('volume') or 1.0)))
   p=root/'volume-changed.mp3';run(['ffmpeg','-y','-i',str(src),'-vn','-af',f'volume={volume}', '-c:a','libmp3lame','-b:a','192k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='audio-reverse':
   p=root/'reversed.mp3';run(['ffmpeg','-y','-i',str(src),'-vn','-af','areverse','-c:a','libmp3lame','-b:a','192k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='audio-loop':
   loops=max(1,min(60,int(o.get('loops') or 2)))-1
   p=root/'looped.mp3';run(['ffmpeg','-y','-stream_loop',str(loops),'-i',str(src),'-vn','-c:a','libmp3lame','-b:a','192k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='audio-compress':
   bitrate=max(64,min(160,int(o.get('bitrate') or 96)))
   p=root/'compressed.mp3';run(['ffmpeg','-y','-i',str(src),'-vn','-c:a','libmp3lame','-b:a',f'{bitrate}k',str(p)])
   return res(p,root,'audio/mpeg',p.name)
  if a=='mp4-to-gif':
   p=root/'converted.gif';run(['ffmpeg','-y','-i',str(src),'-vf','fps=10,scale=720:-1:flags=lanczos' ,'-an',str(p)])
   return res(p,root,'image/gif',p.name)
  if a=='video-merge':
   if len(ins)<2:raise HTTPException(400,'Choose at least two video files.')
   listfile=root/'videos.txt'
   with listfile.open('w',encoding='utf8') as f:
    for x in ins:f.write("file "+str(x).replace("'","'\\''")+"\\n")
   p=root/'merged.mp4';run(['ffmpeg','-y',*[x for pair in [['-i',str(src)] for src in ins] for x in pair],'-filter_complex',f'concat=n={len(ins)}:v=1:a=1','-c:v','libx264','-crf','23','-preset','fast','-c:a','aac','-b:a','128k',str(p)])
   return res(p,root,'video/mp4',p.name)
  if a=='video-speed':
   speed=max(.25,min(4.0,float(o.get('speed') or 1.0)))
   vf=f'setpts={1/speed:.6f}*PTS'
   filters=[];remain=speed
   while remain>2:filters.append('atempo=2');remain/=2
   while remain<0.5:filters.append('atempo=0.5');remain/=0.5
   filters.append(f'atempo={remain:.4f}')
   p=root/'speed-changed.mp4';run(['ffmpeg','-y','-i',str(src),'-vf',vf,'-af',','.join(filters),'-c:v','libx264','-crf','23','-preset','fast','-c:a','aac','-b:a','128k',str(p)])
   return res(p,root,'video/mp4',p.name)
  if a=='video-mute':
   p=root/'muted.mp4';run(['ffmpeg','-y','-i',str(src),'-an','-c:v','libx264','-crf','23','-preset','fast',str(p)])
   return res(p,root,'video/mp4',p.name)
  if a=='video-resize':
   width=int(o.get('width') or 1280);height=int(o.get('height') or 720)
   p=root/'resized.mp4';run(['ffmpeg','-y','-i',str(src),'-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2','-c:v','libx264','-crf','23','-preset','fast','-c:a','aac','-b:a','128k',str(p)])
   return res(p,root,'video/mp4',p.name)
  if a=='video-crop':
   width=int(o.get('width') or 720);height=int(o.get('height') or 720);x=int(o.get('x') or 0);y=int(o.get('y') or 0)
   p=root/'cropped.mp4';run(['ffmpeg','-y','-i',str(src),'-vf',f'crop={width}:{height}:{x}:{y}','-c:v','libx264','-crf','23','-preset','fast','-c:a','aac','-b:a','128k',str(p)])
   return res(p,root,'video/mp4',p.name)
  mp={'mp3-to-wav':('converted.wav',['-vn','-acodec','pcm_s16le']),'wav-to-mp3':('converted.mp3',['-vn','-codec:a','libmp3lame','-b:a','192k']),'mp3-to-ogg':('converted.ogg',['-vn','-codec:a','libvorbis','-q:a','5']),'mp4-to-webm':('converted.webm',['-c:v','libvpx-vp9','-crf','32','-b:v','0','-c:a','libopus']),'webm-to-mp4':('converted.mp4',['-c:v','libx264','-crf','23','-c:a','aac']),'video-compress':('compressed.mp4',['-c:v','libx264','-crf','30','-preset','medium','-c:a','aac','-b:a','96k']),'video-trim':('trimmed.mp4',['-ss',start or '00:00:00','-i',str(src),'-t',duration or '00:00:10','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-b:a','128k']),'video-to-mp3':('audio.mp3',['-vn','-codec:a','libmp3lame','-b:a','192k'])}
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
  if a=='delete-pages':
   raw=str(o.get('pages') or '').strip()
   if not raw:raise HTTPException(400,'Select at least one page to delete.')
   try:ids=sorted(set(int(x)-1 for x in raw.split(',') if x.strip()))
   except:raise HTTPException(400,'Pages must be numbers separated by commas.')
   if any(i<0 or i>=len(d) for i in ids):raise HTTPException(400,f'Page number is outside the PDF range 1-{len(d)}.')
   if len(ids)>=len(d):raise HTTPException(400,'You cannot delete every page. Keep at least one page.')
   for i in reversed(ids):d.delete_page(i)
   p=root/'pages-deleted.pdf';savepdf(d,p);d.close();return res(p,root,'application/pdf',p.name)
  if a=='split-pdf':
   folder=root/'split-pages';folder.mkdir()
   for i in range(len(d)):
    one=fitz.open();one.insert_pdf(d,from_page=i,to_page=i);savepdf(one,folder/f'page-{i+1}.pdf');one.close()
   d.close();z=Path(shutil.make_archive(str(root/'split-pages'),'zip',root_dir=folder));return res(z,root,'application/zip','split-pages.zip')
  if a=='extract-pages':
   raw=str(o.get('pages') or o.get('order') or '').strip()
   if not raw:raise HTTPException(400,'Enter page numbers such as 1,3,5.')
   try:ids=sorted(set(int(x)-1 for x in raw.split(',') if x.strip()))
   except:raise HTTPException(400,'Page numbers must be comma-separated numbers.')
   if not ids or any(i<0 or i>=len(d) for i in ids):raise HTTPException(400,f'Page number is outside the PDF range 1-{len(d)}.')
   out=fitz.open()
   for i in ids:out.insert_pdf(d,from_page=i,to_page=i)
   p=root/'extracted-pages.pdf';savepdf(out,p);out.close();d.close();return res(p,root,'application/pdf',p.name)
  if a in {'organize-pdf','rearrange-pages','duplicate-pages','add-pages'}:
   ids=list(range(len(d)))
   if a in {'organize-pdf','rearrange-pages'}:
    raw=str(o.get('order') or '').strip()
    if raw:
     try:ids=[int(x)-1 for x in raw.split(',') if x.strip()]
     except:raise HTTPException(400,'Page order must be comma-separated numbers.')
     if not ids or any(i<0 or i>=len(d) for i in ids):raise HTTPException(400,f'Page order contains a page outside 1-{len(d)}.')
   if a=='duplicate-pages':
    raw=str(o.get('pages') or o.get('order') or '').strip()
    if raw:
     try:dup=[int(x)-1 for x in raw.split(',') if x.strip()]
     except:raise HTTPException(400,'Page numbers must be comma-separated numbers.')
     if any(i<0 or i>=len(d) for i in dup):raise HTTPException(400,f'Page number is outside the PDF range 1-{len(d)}.')
     ids=ids+dup
    elif ids:ids=ids+[ids[0]]
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
   text=str(o.get('text') or signature or 'File Tools ARK');page_no=max(1,int(o.get('page',1)));x=float(o.get('x',45));y=float(o.get('y',55));size=float(o.get('size',14))
   if page_no>len(d):raise HTTPException(400,f'Page number is outside 1-{len(d)}.')
   d[page_no-1].insert_text((x,y),text,fontsize=size)
  elif a=='add-image-pdf':
   if len(ins)<2:raise HTTPException(400,'Upload PDF and image together.')
   page_no=max(1,int(o.get('page',1)));x=float(o.get('x',45));y=float(o.get('y',45));width=float(o.get('width',175));height=float(o.get('height',135))
   if page_no>len(d):raise HTTPException(400,f'Page number is outside 1-{len(d)}.')
   d[page_no-1].insert_image(fitz.Rect(x,y,x+width,y+height),filename=str(ins[1]))
  elif a=='annotate-pdf':
   page_no=max(1,int(o.get('page',1)));x=float(o.get('x',70));y=float(o.get('y',70));text=str(o.get('text') or 'Annotation')
   if page_no>len(d):raise HTTPException(400,f'Page number is outside 1-{len(d)}.')
   d[page_no-1].add_text_annot((x,y),text)
  elif a=='highlight-pdf':
   term=str(o.get('text') or signature or '').strip()
   if not term:raise HTTPException(400,'Enter text to highlight.')
   for p in d:
    for r in p.search_for(term):p.add_highlight_annot(r).update()
  elif a=='add-shapes-pdf':
   page_no=max(1,int(o.get('page',1)));x=float(o.get('x',45));y=float(o.get('y',45));width=float(o.get('width',175));height=float(o.get('height',105));shape=str(o.get('shape','rectangle')).lower();sw=float(o.get('stroke',2))
   if page_no>len(d):raise HTTPException(400,f'Page number is outside 1-{len(d)}.')
   p=d[page_no-1];r=fitz.Rect(x,y,x+width,y+height)
   if shape=='circle':p.draw_oval(r,color=(.2,.35,.45),width=sw)
   elif shape=='line':p.draw_line((x,y),(x+width,y+height),color=(.2,.35,.45),width=sw)
   else:p.draw_rect(r,color=(.2,.35,.45),width=sw)
  elif a=='draw-pdf':
   page_no=max(1,int(o.get('page',1)));pts=o.get('points',[])
   if page_no>len(d):raise HTTPException(400,f'Page number is outside 1-{len(d)}.')
   if not isinstance(pts,list) or len(pts)<2:raise HTTPException(400,'Provide at least two drawing points.')
   p=d[page_no-1]
   for a1,b1 in zip(pts,pts[1:]):p.draw_line((float(a1[0]),float(a1[1])),(float(b1[0]),float(b1[1])),color=(.1,.1,.1),width=float(o.get('stroke',2)))
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
