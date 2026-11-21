// Small helpers for talking to the LessonForge backend.
async function parse(response) {
  const raw = await response.text();
  let data = null;
  try { data = raw ? JSON.parse(raw) : null; } catch { /* not JSON */ }
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : (raw && raw.length < 300 ? raw : `Request failed (${response.status}).`));
  }
  return data;
}

const json = (method, body) => ({ method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  capabilities: () => fetch('/api/capabilities').then(parse),
  startLesson: (payload) => fetch('/api/lessons/generate-async', json('POST', payload)).then(parse),
  job: (id) => fetch(`/api/jobs/${id}`).then(parse),
  extractSource: (file) => { const form = new FormData(); form.append('file', file); return fetch('/api/sources/extract', { method: 'POST', body: form }).then(parse); },
  library: () => fetch('/api/library').then(parse),
  saveToLibrary: (lesson) => fetch('/api/library', json('POST', lesson)).then(parse),
  getLesson: (id) => fetch(`/api/library/${id}`).then(parse),
  deleteLesson: (id) => fetch(`/api/library/${id}`, { method: 'DELETE' }).then(parse),
  getQuiz: (id) => fetch(`/api/quiz/${id}`).then(parse),
  quiz: (id) => fetch(`/api/quiz/${id}`, { method: 'POST' }).then(parse),
  newQuiz: (id) => fetch(`/api/quiz/${id}/regenerate`, { method: 'POST' }).then(parse),
  ask: (payload) => fetch('/api/ask', json('POST', payload)).then(parse),
  tts: (payload) => fetch('/api/tts', json('POST', payload)).then(parse),
  startVideo: (payload) => fetch('/api/video', json('POST', payload)).then(parse),
  videos: (id) => fetch(`/api/library/${id}/videos`).then(parse),
};

/** Poll a background job until it finishes. onUpdate gets {progress, message}. */
export async function waitForJob(jobId, onUpdate, { interval = 1200, signal } = {}) {
  for (;;) {
    if (signal?.aborted) throw new Error('Cancelled');
    const job = await api.job(jobId);
    onUpdate?.(job);
    if (job.status === 'done') return job.result;
    if (job.status === 'error') throw new Error(job.error || 'The job failed.');
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}
