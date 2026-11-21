import { useEffect, useRef, useState } from 'react';
import { Download, GraduationCap, Upload } from 'lucide-react';
import Home from './Home';
import LessonView from './LessonView';
import RenderPage from './RenderPage';
import { api } from './api';

function readHash() {
  const hash = window.location.hash || '';
  const render = hash.match(/^#\/render\/([\w-]+)/);
  if (render) return { type: 'render', id: render[1] };
  const shared = hash.match(/^#\/lesson\/([\w-]+)/);
  if (shared) return { type: 'lesson', id: shared[1] };
  return { type: 'home' };
}

function validLesson(data) {
  return data && typeof data.title === 'string' && typeof data.topic === 'string' && typeof data.introduction === 'string'
    && Array.isArray(data.sections) && data.sections.length >= 1
    && data.sections.every((s) => typeof s.heading === 'string' && typeof s.narration === 'string' && s.slide && typeof s.slide.title === 'string' && Array.isArray(s.slide.bullet_points));
}

export default function App() {
  const [route, setRoute] = useState(readHash);
  const [lesson, setLesson] = useState(null);
  const [error, setError] = useState('');
  const [caps, setCaps] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    const onHash = () => setRoute(readHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  useEffect(() => { if (route.type !== 'render') api.capabilities().then(setCaps).catch(() => setCaps(null)); }, [route.type]);

  // open a shared link: #/lesson/<id>
  useEffect(() => {
    if (route.type === 'lesson' && route.id && lesson?.id !== route.id) {
      api.getLesson(route.id).then(setLesson).catch((err) => { setError(err.message); window.location.hash = ''; });
    }
  }, [route]); // eslint-disable-line

  if (route.type === 'render') return <RenderPage videoId={route.id} />;

  function openLesson(data) {
    setError('');
    setLesson(data);
    if (data.id) window.history.replaceState(null, '', `#/lesson/${data.id}`);
  }
  function closeLesson() {
    setLesson(null);
    window.history.replaceState(null, '', window.location.pathname);
    setRoute({ type: 'home' });
  }

  async function loadFile(event) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      if (!validLesson(data)) throw new Error('This file is not a valid LessonForge lesson.');
      delete data.id;
      openLesson(data);
    } catch (err) {
      setError(err instanceof SyntaxError ? 'The selected file is not valid JSON.' : (err.message || 'Could not load this lesson file.'));
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar no-print">
        <a className="brand" href="#" onClick={(e) => { e.preventDefault(); closeLesson(); }} aria-label="LessonForge home">
          <span className="brand-mark"><GraduationCap size={22} /></span>
          <span>Lesson<span className="brand-accent">Forge</span></span>
        </a>
        <div className="topbar-actions">
          <input ref={fileRef} className="file-input-hidden" type="file" accept=".json,application/json" onChange={loadFile} />
          <button className="topbar-action" onClick={() => fileRef.current?.click()}><Upload size={15} /> Open lesson file</button>
          <div className="topbar-note"><span className="status-dot" /> AI-powered learning studio</div>
        </div>
      </header>

      <main className="main-wrap">
        {!lesson && <Home onOpen={openLesson} onError={setError} error={error} />}
        {lesson && <LessonView key={lesson.id || lesson.title} initialLesson={lesson} onBack={closeLesson} caps={caps} />}
      </main>
      <footer className="footer no-print">LESSONFORGE <span>•</span> AI LESSON GENERATOR</footer>
    </div>
  );
}
