import { useEffect, useRef, useState } from 'react';
import { AlertCircle, BookOpen, FileText, LoaderCircle, Sparkles, Trash2, Upload, X } from 'lucide-react';
import { api, waitForJob } from './api';
import { LANGUAGES, LEVELS, loadSetting, saveSetting } from './lecturers';
import { getProgress } from './progress';

export default function Home({ onOpen, onError, error }) {
  const [topic, setTopic] = useState('');
  const [script, setScript] = useState('');
  const [language, setLanguage] = useState(() => loadSetting('language', 'English'));
  const [level, setLevel] = useState(() => loadSetting('level', 'intermediate'));
  const [material, setMaterial] = useState(null); // {filename, text}
  const [busy, setBusy] = useState(null);         // {progress, message}
  const [uploading, setUploading] = useState(false);
  const [library, setLibrary] = useState([]);
  const fileRef = useRef(null);

  const refreshLibrary = () => api.library().then(setLibrary).catch(() => setLibrary([]));
  useEffect(() => { refreshLibrary(); }, []);

  async function attach(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    setUploading(true); onError('');
    try {
      const res = await api.extractSource(file);
      setMaterial({ filename: res.filename, text: res.text, characters: res.characters });
      if (!topic.trim()) setTopic((res.filename || '').replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').slice(0, 120));
    } catch (err) { onError(err.message); } finally { setUploading(false); }
  }

  async function generate(event) {
    event.preventDefault();
    if (topic.trim().length < 3) { onError('Enter a lesson topic first (at least 3 characters).'); return; }
    saveSetting('language', language); saveSetting('level', level);
    onError(''); setBusy({ progress: 2, message: 'Starting…' });
    try {
      const { job_id: jobId } = await api.startLesson({ topic: topic.trim(), script: script.trim() || null, language, level, material: material?.text || null });
      const lesson = await waitForJob(jobId, (job) => setBusy({ progress: job.progress, message: job.message }));
      onOpen(lesson);
    } catch (err) {
      onError(`${err.message} Make sure the backend is running at http://127.0.0.1:8000.`);
    } finally { setBusy(null); }
  }

  async function open(id) {
    try { onOpen(await api.getLesson(id)); } catch (err) { onError(err.message); }
  }
  async function remove(id) {
    if (!window.confirm('Delete this lesson from your library?')) return;
    try { await api.deleteLesson(id); refreshLibrary(); } catch (err) { onError(err.message); }
  }

  return (
    <>
      <section className="hero">
        <div className="eyebrow"><Sparkles size={14} /> YOUR PERSONAL LEARNING STUDIO</div>
        <h1>Turn any topic into<br /><span>a lecture worth watching.</span></h1>
        <p className="hero-copy">A human lecturer with a natural voice teaches you at the board, with diagrams that build as they speak. Take quizzes, ask questions, and export the lecture as a video.</p>
        <form className="generator-card" onSubmit={generate}>
          <label htmlFor="topic">What do you want to learn?</label>
          <input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. How artificial intelligence works" disabled={!!busy} />

          <div className="option-row">
            <label className="mini-field">LANGUAGE
              <select value={language} onChange={(e) => setLanguage(e.target.value)} disabled={!!busy}>{LANGUAGES.map((l) => <option key={l}>{l}</option>)}</select>
            </label>
            <div className="mini-field">LEVEL
              <div className="chips">{LEVELS.map((l) => <button type="button" key={l.id} className={level === l.id ? 'on' : ''} onClick={() => setLevel(l.id)} disabled={!!busy}>{l.label}</button>)}</div>
            </div>
          </div>

          <label htmlFor="script" className="optional-label">Notes, outline or your own material <span>OPTIONAL</span></label>
          <textarea id="script" value={script} onChange={(e) => setScript(e.target.value)} placeholder="Paste your lecturer's notes or lesson outline here..." rows="3" disabled={!!busy} />
          <div className="upload-row">
            <input ref={fileRef} className="file-input-hidden" type="file" accept=".pdf,.docx,.txt,.md" onChange={attach} />
            {material ? (
              <span className="file-chip"><FileText size={14} /> {material.filename} · {Math.round(material.characters / 1000)}k characters <button type="button" onClick={() => setMaterial(null)} aria-label="Remove file"><X size={13} /></button></span>
            ) : (
              <button type="button" className="upload-button" onClick={() => fileRef.current?.click()} disabled={uploading || !!busy}>
                {uploading ? <LoaderCircle className="spin" size={15} /> : <Upload size={15} />} Teach from a PDF, Word or text file
              </button>
            )}
          </div>

          {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}
          {busy ? (
            <div className="job-progress" role="status">
              <div className="job-top"><LoaderCircle className="spin" size={17} /> {busy.message}</div>
              <div className="progress-track"><div style={{ width: `${busy.progress}%` }} /></div>
              <small>This usually takes 30–90 seconds: research, writing, diagrams and a quality check.</small>
            </div>
          ) : (
            <button className="generate-button" type="submit"><Sparkles size={18} /> Generate lesson</button>
          )}
          <div className="form-foot"><BookOpen size={14} /> Every lesson is saved to your library automatically.</div>
        </form>
      </section>

      {library.length > 0 && (
        <section className="library">
          <div className="section-kicker">YOUR LIBRARY</div>
          <div className="library-grid">
            {library.map((item) => {
              const done = getProgress(item.id).visited.length;
              return (
                <article key={item.id} className="library-card">
                  <button className="library-open" onClick={() => open(item.id)}>
                    <h3>{item.title}</h3>
                    <p>{item.topic}</p>
                    <div className="library-meta"><span>{item.sections} sections</span><span>{item.language}</span><span>{new Date(item.created_at * 1000).toLocaleDateString()}</span></div>
                    <div className="progress-track small"><div style={{ width: `${Math.min(100, (done / Math.max(1, item.sections)) * 100)}%` }} /></div>
                  </button>
                  <button className="library-delete" onClick={() => remove(item.id)} aria-label={`Delete ${item.title}`}><Trash2 size={15} /></button>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </>
  );
}
