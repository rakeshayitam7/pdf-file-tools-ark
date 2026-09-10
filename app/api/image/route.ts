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
    if (!(file instanceof File)) return NextResponse.json({ error: 'Choose an image.' }, { status: 400 });
    const input = Buffer.from(await file.arrayBuffer());
    let output: Buffer;
    let type: string;
    let ext: string;
    const image = sharp(input);
    if (format === 'jpg' || format === 'jpeg') { output = await image.jpeg({ quality }).toBuffer(); type='image/jpeg'; ext='jpg'; }
    else if (format === 'webp') { output = await image.webp({ quality }).toBuffer(); type='image/webp'; ext='webp'; }
    else if (format === 'png') { output = await image.png({ compressionLevel: 9 }).toBuffer(); type='image/png'; ext='png'; }
    else return NextResponse.json({ error: 'Unsupported image format.' }, { status: 422 });
    return new NextResponse(output as BodyInit, { headers: { 'Content-Type': type, 'Content-Disposition': `attachment; filename="ark-converted.${ext}"`, 'Cache-Control': 'no-store' } });
  } catch (e) { console.error(e); return NextResponse.json({ error: 'Image processing failed.' }, { status: 500 }); }
}
