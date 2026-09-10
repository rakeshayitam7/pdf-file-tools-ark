# ARK File Processing Worker

This service is the heavy-processing layer for PDF & File Tools ARK.

## Engines
- PyMuPDF: PDF text extraction and PDF page rendering
- qpdf: PDF stream/object compression
- python-docx: PDF text -> DOCX
- LibreOffice: DOCX/PPTX/XLSX -> PDF
- Playwright Chromium: HTML -> PDF
- FFmpeg: audio/video conversion, compression and trimming

## Run locally
```bash
docker build -t ark-file-worker ./worker
docker run --rm -p 8080:8080 -e FILE_WORKER_API_KEY=change-me ark-file-worker
```
Health check: `GET /health`

## Connect to Vercel
Deploy this Docker image to a container service such as Google Cloud Run, Railway, Render, AWS ECS/Fargate or another Docker-capable host. Then add these Vercel environment variables:

- `FILE_WORKER_URL=https://YOUR-WORKER-HOST`
- `FILE_WORKER_API_KEY=the-same-random-secret-used-by-the-worker`

Redeploy the Next.js app after setting the variables.

The Next.js `/api/process` route keeps lightweight PDF/document operations local and forwards heavy operations to this worker. The browser never receives the worker secret.

## Security notes
- Keep the worker private if your hosting platform supports private ingress.
- Always set a long random `FILE_WORKER_API_KEY`.
- Keep `MAX_FILE_BYTES` appropriate for your plan.
- Add rate limiting/authentication before opening the service publicly.
- Worker files are written to an isolated temporary directory and cleaned after the response.
