export async function forwardToWorker(form: FormData): Promise<Response | null> {
  const baseUrl = process.env.FILE_WORKER_URL?.replace(/\/$/, '');
  if (!baseUrl) return null;

  const headers: Record<string, string> = {};
  if (process.env.FILE_WORKER_API_KEY) headers['x-ark-worker-key'] = process.env.FILE_WORKER_API_KEY;

  const response = await fetch(`${baseUrl}/process`, {
    method: 'POST',
    body: form,
    headers,
    cache: 'no-store',
  });

  return response;
}
