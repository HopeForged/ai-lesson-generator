import { useEffect, useState } from 'react';
import { AlertCircle, Download, Film, LoaderCircle } from 'lucide-react';
import { api, waitForJob } from './api';

export default function VideoPanel({ lesson, lecturer, rate, caps, ensureSaved }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [past, setPast] = useState([]);
  const [silent, setSilent] = useState(false);

  useEffect(() => { if (lesson.id) api.videos(lesson.id).then(setPast).catch(() => {}); }, [lesson.id, result]);

  async function make() {
    setError(''); setResult(null); setBusy({ progress: 1, message: 'Starting…' });
    try {
      const id = await ensureSaved();
      const { job_id: jobId } = await api.startVideo({ lesson_id: id, lecturer, rate, allow_silent: silent });
      setResult(await waitForJob(jobId, (job) => setBusy({ progress: job.progress, message: job.message }), { interval: 1500 }));
    } catch (err) { setError(err.message); } finally { setBusy(null); }
  }

  const shown = result ? { url: result.url, captions: result.captions, has_voice: result.has_voice, duration: result.duration } : null;
  return (
    <div className="video-panel no-print">
      <div className="narration-title"><Film size={16} /> LECTURE VIDEO <span className="narration-hint">Free MP4 with voice, diagrams and captions</span></div>
      <p className="quiz-hint">Records the whole lecture with {lecturer === 'naledi' ? 'Prof. Naledi' : lecturer === 'walker' ? 'Mr. Walker' : 'Dr. Mensah'} exactly as you see it here. Recording runs in real time, so a 10-minute lecture takes about 12 minutes. You can keep using the app meanwhile.</p>
      {!caps?.voice && <label className="silent-opt"><input type="checkbox" checked={silent} onChange={(e) => setSilent(e.target.checked)} /> The free voice engine is not installed — create a captions-only video without sound (install it with <code>pip install edge-tts</code> for narration).</label>}
      {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}
      {busy ? (
        <div className="job-progress"><div className="job-top"><LoaderCircle className="spin" size={16} /> {busy.message} <b>{busy.progress}%</b></div><div className="progress-track"><div style={{ width: `${busy.progress}%` }} /></div></div>
      ) : (
        <button className="primary" onClick={make}><Film size={16} /> Create video</button>
      )}
      {caps && (
        <ul className="req-list">
          <li className={caps.ffmpeg ? 'ok' : 'bad'}>{caps.ffmpeg ? '✓' : '✗'} ffmpeg {!caps.ffmpeg && <>— install it (<code>winget install ffmpeg</code>), then restart the backend terminal</>}</li>
          <li className={caps.playwright ? 'ok' : 'bad'}>{caps.playwright ? '✓' : '✗'} Playwright {!caps.playwright && <>— run <code>pip install playwright</code> then <code>playwright install chromium</code></>}</li>
          <li className={caps.voice ? 'ok' : 'bad'}>{caps.voice ? '✓' : '✗'} Natural voice (edge-tts) {!caps.voice && <>— run <code>pip install edge-tts</code></>}</li>
        </ul>
      )}
      {shown && (
        <div className="video-result">
          <video controls src={shown.url} />
          <div className="video-links"><a href={shown.url} download><Download size={15} /> Download MP4</a><a href={shown.captions} download><Download size={15} /> Captions (.srt)</a>{!shown.has_voice && <span>Captions-only (no voice)</span>}</div>
        </div>
      )}
      {!shown && past.length > 0 && (
        <div className="video-past">Earlier videos: {past.map((v) => <a key={v.id} href={v.url} target="_blank" rel="noreferrer">{new Date(v.created_at * 1000).toLocaleString()}</a>)}</div>
      )}
    </div>
  );
}
