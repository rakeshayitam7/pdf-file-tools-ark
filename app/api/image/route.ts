import { NextResponse } from 'next/server';
import sharp from 'sharp';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  try {
    const form = await request.formData();
    const file = form.get('file');
    const format = String(form.get('format') || 'png');
    const quality = Math.max(1, Math.min(100, Number(form.get('quality') || 82)));
    const width = Number(form.get('width') || 0);
    const height = Number(form.get('height') || 0);
    const left = Number(form.get('left') || 0);
    const top = Number(form.get('top') || 0);
    if (!(file instanceof File)) return NextResponse.json({ error: 'Choose an image.' }, { status: 400 });
    const input = Buffer.from(await file.arrayBuffer());
    let image = sharp(input);

    if (format === 'resize') {
      if (!width && !height) return NextResponse.json({ error: 'Enter width or height.' }, { status: 400 });
      image = image.resize({ width: width || undefined, height: height || undefined, fit: 'inside', withoutEnlargement: true });
      const output = await image.webp({ quality }).toBuffer();
      return new NextResponse(output as BodyInit, { headers: { 'Content-Type': 'image/webp', 'Content-Disposition': 'attachment; filename="ark-resized.webp"', 'Cache-Control': 'no-store' } });
    }

    if (format === 'crop') {
      if (!width || !height) return NextResponse.json({ error: 'Enter crop width and height.' }, { status: 400 });
      const output = await image.extract({ left: Math.max(0, left), top: Math.max(0, top), width, height }).webp({ quality }).toBuffer();
      return new NextResponse(output as BodyInit, { headers: { 'Content-Type': 'image/webp', 'Content-Disposition': 'attachment; filename="ark-cropped.webp"', 'Cache-Control': 'no-store' } });
    }

    if (format === 'compress') {
      const output = await image.webp({ quality }).toBuffer();
      return new NextResponse(output as BodyInit, { headers: { 'Content-Type': 'image/webp', 'Content-Disposition': 'attachment; filename="ark-compressed.webp"', 'Cache-Control': 'no-store' } });
    }

    let output: Buffer;
    let type: string;
    let ext: string;
    if (format === 'jpg' || format === 'jpeg') { output = await image.jpeg({ quality, mozjpeg: true }).toBuffer(); type = 'image/jpeg'; ext = 'jpg'; }
    else if (format === 'webp') { output = await image.webp({ quality }).toBuffer(); type = 'image/webp'; ext = 'webp'; }
    else if (format === 'png') { output = await image.png({ compressionLevel: 9 }).toBuffer(); type = 'image/png'; ext = 'png'; }
    else return NextResponse.json({ error: 'Unsupported image operation.' }, { status: 422 });
    return new NextResponse(output as BodyInit, { headers: { 'Content-Type': type, 'Content-Disposition': `attachment; filename="ark-converted.${ext}"`, 'Cache-Control': 'no-store' } });
  } catch (e) { console.error(e); return NextResponse.json({ error: 'Image processing failed. Check the image and crop dimensions.' }, { status: 500 }); }
}
