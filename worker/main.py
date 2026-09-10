import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import fitz
from docx import Document
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

app = FastAPI(title="PDF & File Tools ARK Worker", version="1.0.0")
MAX_FILE_BYTES = int(os.getenv("MAX_FILE_BYTES", str(100 * 1024 * 1024)))
AUDIO_VIDEO = {"mp3-to-wav", "wav-to-mp3", "mp3-to-ogg", "audio-compress", "mp4-to-webm", "webm-to-mp4", "mp4-to-gif", "video-compress", "video-trim", "video-to-mp3"}
OFFICE = {"word-to-pdf", "ppt-to-pdf", "excel-to-pdf", "pptx-to-images"}


def run(cmd: list[str], cwd: Path | None = None):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-3000:] or "Processing command failed")


async def save_upload(upload: UploadFile, folder: Path, index: int) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix.lower()
    path = folder / f"input-{index}{suffix}"
    total = 0
    with path.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise HTTPException(413, "File is too large for the processing worker.")
            out.write(chunk)
    return path


def result(path: Path, media_type: str | None = None, filename: str | None = None):
    return FileResponse(path, media_type=media_type, filename=filename or path.name, headers={"Cache-Control": "no-store"})


def ffmpeg(input_path: Path, output_path: Path, args: list[str]):
    run(["ffmpeg", "-y", "-i", str(input_path), *args, str(output_path)])


@app.get("/health")
def health():
    return {"ok": True, "service": "ark-file-worker"}


@app.post("/process")
async def process(
    action: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()] = [],
    signature: Annotated[str | None, Form()] = None,
    start: Annotated[str | None, Form()] = None,
    duration: Annotated[str | None, Form()] = None,
    quality: Annotated[str | None, Form()] = None,
    html: Annotated[str | None, Form()] = None,
):
    if not files and action != "html-to-pdf":
        raise HTTPException(400, "At least one file is required.")
    with tempfile.TemporaryDirectory(prefix="ark-worker-") as tmp:
        root = Path(tmp)
        inputs = [await save_upload(f, root / f"in{i}", i) for i, f in enumerate(files)]
        return await dispatch(action, inputs, root, signature, start, duration, quality, html)


async def dispatch(action, inputs, root, signature, start, duration, quality, html):
    if action in {"pdf-to-jpg", "pdf-to-png", "pdf-to-text", "pdf-to-word", "compress-pdf"}:
        src = inputs[0]
        if action == "pdf-to-text":
            doc = fitz.open(src)
            text = "\n\n".join(page.get_text("text") for page in doc)
            out = root / "document.txt"
            out.write_text(text, encoding="utf-8")
            return result(out, "text/plain; charset=utf-8", "document.txt")
        if action == "pdf-to-word":
            doc = fitz.open(src)
            out = root / "document.docx"
            word = Document()
            for i, page in enumerate(doc):
                if i:
                    word.add_page_break()
                for block in page.get_text("blocks"):
                    text = block[4].strip()
                    if text:
                        word.add_paragraph(text)
            word.save(out)
            return result(out, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "document.docx")
        if action in {"pdf-to-jpg", "pdf-to-png"}:
            doc = fitz.open(src)
            ext = "jpg" if action == "pdf-to-jpg" else "png"
            outputs = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
                out = root / f"page-{i+1}.{ext}"
                pix.save(out)
                outputs.append(out)
            if len(outputs) == 1:
                return result(outputs[0], f"image/{ext}", outputs[0].name)
            archive = Path(shutil.make_archive(str(root / f"pdf-pages-{ext}"), "zip", root_dir=root, base_dir="."))
            return result(archive, "application/zip", archive.name)
        if action == "compress-pdf":
            out = root / "compressed.pdf"
            run(["qpdf", "--object-streams=generate", "--compress-streams=y", str(src), str(out)])
            return result(out, "application/pdf", "compressed.pdf")

    if action in OFFICE:
        src = inputs[0]
        outdir = root / "converted"
        outdir.mkdir()
        run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(src)])
        pdf = next(outdir.glob("*.pdf"), None)
        if not pdf:
            raise RuntimeError("LibreOffice did not produce a PDF.")
        if action == "pptx-to-images":
            doc = fitz.open(pdf)
            slide_dir = root / "slides"
            slide_dir.mkdir()
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                pix.save(slide_dir / f"slide-{i+1}.png")
            archive = Path(shutil.make_archive(str(root / "slides"), "zip", root_dir=slide_dir))
            return result(archive, "application/zip", "slides.zip")
        return result(pdf, "application/pdf", "converted.pdf")

    if action == "html-to-pdf":
        if not html:
            raise HTTPException(400, "HTML content is required.")
        from playwright.async_api import async_playwright
        out = root / "webpage.pdf"
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            await page.pdf(path=str(out), format="A4", print_background=True)
            await browser.close()
        return result(out, "application/pdf", "webpage.pdf")

    if action in AUDIO_VIDEO:
        src = inputs[0]
        q = max(1, min(100, int(quality or 75)))
        if action == "mp3-to-wav": out, args = root / "converted.wav", ["-vn", "-acodec", "pcm_s16le"]
        elif action == "wav-to-mp3": out, args = root / "converted.mp3", ["-vn", "-codec:a", "libmp3lame", "-b:a", "192k"]
        elif action == "mp3-to-ogg": out, args = root / "converted.ogg", ["-vn", "-codec:a", "libvorbis", "-q:a", "5"]
        elif action == "audio-compress": out, args = root / "compressed.mp3", ["-vn", "-codec:a", "libmp3lame", "-b:a", f"{max(64, int(q * 2))}k"]
        elif action == "mp4-to-webm": out, args = root / "converted.webm", ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"]
        elif action == "webm-to-mp4": out, args = root / "converted.mp4", ["-c:v", "libx264", "-crf", "23", "-c:a", "aac"]
        elif action == "mp4-to-gif": out, args = root / "converted.gif", ["-vf", "fps=10,scale=720:-1:flags=lanczos", "-an"]
        elif action == "video-compress": out, args = root / "compressed.mp4", ["-c:v", "libx264", "-crf", "30", "-preset", "medium", "-c:a", "aac", "-b:a", "96k"]
        elif action == "video-trim":
            if not start or not duration:
                raise HTTPException(400, "Start time and duration are required.")
            out, args = root / "trimmed.mp4", ["-ss", start, "-t", duration, "-c", "copy"]
        else:
            out, args = root / "audio.mp3", ["-vn", "-codec:a", "libmp3lame", "-b:a", "192k"]
        ffmpeg(src, out, args)
        mime = {".mp3":"audio/mpeg", ".wav":"audio/wav", ".ogg":"audio/ogg", ".mp4":"video/mp4", ".webm":"video/webm", ".gif":"image/gif"}.get(out.suffix, "application/octet-stream")
        return result(out, mime, out.name)

    raise HTTPException(422, f"Worker action not implemented: {action}")
