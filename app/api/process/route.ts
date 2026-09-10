import { NextResponse } from 'next/server';
import { PDFDocument, degrees, rgb, StandardFonts } from 'pdf-lib';
import mammoth from 'mammoth';
import * as XLSX from 'xlsx';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

function download(data: Uint8Array | Buffer, filename: string, type = 'application/pdf') {
  return new NextResponse(data as BodyInit, { headers: { 'Content-Type': type, 'Content-Disposition': `attachment; filename="${filename}"`, 'Cache-Control': 'no-store' } });
}

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const action = String(form.get('action') || '');
    const uploads = form.getAll('files').filter((x): x is File => x instanceof File);
    if (!uploads.length) return NextResponse.json({ error: 'Please choose at least one file.' }, { status: 400 });

    if (action === 'merge-pdf') {
      const out = await PDFDocument.create();
      for (const file of uploads) {
        const src = await PDFDocument.load(await file.arrayBuffer());
        const pages = await out.copyPages(src, src.getPageIndices());
        pages.forEach(p => out.addPage(p));
      }
      return download(await out.save(), 'merged.pdf');
    }

    if (action === 'jpg-to-pdf' || action === 'png-to-pdf') {
      const out = await PDFDocument.create();
      const expected = action === 'jpg-to-pdf' ? ['.jpg', '.jpeg'] : ['.png'];
      const valid = uploads.filter(f => expected.some(ext => f.name.toLowerCase().endsWith(ext)));
      if (!valid.length) return NextResponse.json({ error: `Choose ${action === 'jpg-to-pdf' ? 'JPG/JPEG' : 'PNG'} images.` }, { status: 400 });
      for (const file of valid) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const image = action === 'jpg-to-pdf' ? await out.embedJpg(bytes) : await out.embedPng(bytes);
        const page = out.addPage([image.width, image.height]);
        page.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
      }
      return download(await out.save(), action === 'jpg-to-pdf' ? 'images-from-jpg.pdf' : 'images-from-png.pdf');
    }

    if (action === 'txt-to-pdf') {
      const text = await uploads[0].text();
      const out = await PDFDocument.create();
      const font = await out.embedFont(StandardFonts.Helvetica);
      const margin = 45, size = 10, lineHeight = 14;
      let page = out.addPage(); let y = page.getHeight() - margin;
      for (const line of text.replace(/\r/g, '').split('\n')) {
        const chunks = line.match(/.{1,105}/g) || [''];
        for (const chunk of chunks) {
          if (y < margin) { page = out.addPage(); y = page.getHeight() - margin; }
          page.drawText(chunk, { x: margin, y, size, font }); y -= lineHeight;
        }
      }
      return download(await out.save(), 'text-document.pdf');
    }

    if (action === 'docx-to-txt') {
      const result = await mammoth.extractRawText({ buffer: Buffer.from(await uploads[0].arrayBuffer()) });
      return download(new TextEncoder().encode(result.value), 'document.txt', 'text/plain; charset=utf-8');
    }

    if (action === 'csv-to-xlsx') {
      const csv = await uploads[0].text();
      const workbook = XLSX.read(csv, { type: 'string' });
      return download(XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' }), 'converted.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    }

    if (action === 'xlsx-to-csv') {
      const workbook = XLSX.read(Buffer.from(await uploads[0].arrayBuffer()), { type: 'buffer' });
      const sheet = workbook.Sheets[workbook.SheetNames[0]];
      const csv = XLSX.utils.sheet_to_csv(sheet);
      return download(new TextEncoder().encode(csv), 'converted.csv', 'text/csv; charset=utf-8');
    }

    const src = await PDFDocument.load(await uploads[0].arrayBuffer());
    const out = await PDFDocument.create();
    let indices = src.getPageIndices();
    if (action === 'delete-first-page') indices = indices.slice(1);
    if (action === 'extract-pages') indices = indices.slice(0, Math.min(2, indices.length));
    if (action === 'split-first-page') indices = indices.slice(0, 1);

    if (action === 'rotate-pdf') {
      const pages = await out.copyPages(src, indices);
      pages.forEach(page => { page.setRotation(degrees((page.getRotation().angle + 90) % 360)); out.addPage(page); });
      return download(await out.save(), 'rotated.pdf');
    }

    if (['delete-first-page', 'extract-pages', 'split-first-page'].includes(action)) {
      const pages = await out.copyPages(src, indices);
      pages.forEach(p => out.addPage(p));
      return download(await out.save(), action === 'split-first-page' ? 'split-page-1.pdf' : `${action}.pdf`);
    }

    if (action === 'watermark' || action === 'page-numbers') {
      const font = await src.embedFont(StandardFonts.Helvetica);
      for (const page of src.getPages()) {
        const { width, height } = page.getSize();
        if (action === 'watermark') page.drawText('PDF & File Tools ARK', { x: width / 2 - 70, y: height / 2, size: 18, font, color: rgb(0.35, 0.35, 0.35), opacity: 0.35, rotate: degrees(30) });
        else page.drawText(`${src.getPages().indexOf(page) + 1}`, { x: width - 35, y: 18, size: 9, font, color: rgb(0.25, 0.25, 0.25) });
      }
      return download(await src.save(), action === 'watermark' ? 'watermarked.pdf' : 'numbered.pdf');
    }

    if (action === 'sign-pdf') {
      const signature = String(form.get('signature') || '').trim();
      if (!signature) return NextResponse.json({ error: 'Enter a signature name or text first.' }, { status: 400 });
      const font = await src.embedFont(StandardFonts.HelveticaOblique);
      for (const page of src.getPages()) page.drawText(signature.slice(0, 80), { x: 45, y: 45, size: 18, font, color: rgb(0.1, 0.1, 0.1) });
      return download(await src.save(), 'signed.pdf');
    }

    if (action === 'metadata') {
      const body = JSON.stringify({ pages: src.getPageCount(), title: src.getTitle() || '', author: src.getAuthor() || '', subject: src.getSubject() || '', creator: src.getCreator() || '', producer: src.getProducer() || '' }, null, 2);
      return download(new TextEncoder().encode(body), 'pdf-metadata.json', 'application/json');
    }

    return NextResponse.json({ error: 'This processor is not enabled yet.' }, { status: 422 });
  } catch (error) {
    console.error(error);
    return NextResponse.json({ error: 'The file could not be processed. Check that it is a valid supported file.' }, { status: 500 });
  }
}
