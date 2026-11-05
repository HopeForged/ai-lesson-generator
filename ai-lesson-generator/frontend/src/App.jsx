import { useEffect, useMemo, useRef, useState } from 'react';
import {
  BookOpen, Play, Pause, SkipBack, SkipForward, Volume2, Sparkles,
  Clock3, ExternalLink, GraduationCap, LoaderCircle, AlertCircle, Download, Upload, Bot
} from 'lucide-react';

const API_URL = '/api/lessons/generate';

export default function App() {
  const [topic, setTopic] = useState('');
  const [script, setScript] = useState('');
  const [lesson, setLesson] = useState(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [voices, setVoices] = useState([]);
  const [voiceName, setVoiceName] = useState('');
  const [rate, setRate] = useState(1);
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const fileInputRef = useRef(null);

  const sections = lesson?.sections ?? [];
  const activeSection = sections[activeIndex];
  const progress = sections.length ? ((activeIndex + 1) / sections.length) * 100 : 0;

  useEffect(() => {
    const loadVoices = () => {
      const available = window.speechSynthesis?.getVoices?.() ?? [];
      setVoices(available);
      if (!voiceName && available.length) setVoiceName(available[0].name);
    };
    loadVoices();
    window.speechSynthesis?.addEventListener?.('voiceschanged', loadVoices);
    return () => {
      window.speechSynthesis?.removeEventListener?.('voiceschanged', loadVoices);
      window.speechSynthesis?.cancel?.();
    };
  }, []);

  useEffect(() => {
    window.speechSynthesis?.cancel?.();
    setSpeaking(false);
    setPaused(false);
  }, [activeIndex, lesson]);

  const selectedVoice = useMemo(
    () => voices.find((voice) => voice.name === voiceName),
    [voices, voiceName]
  );

  async function generateLesson(event) {
    event.preventDefault();
    if (!topic.trim()) {
      setError('Enter a lesson topic first.');
      return;
    }
    window.speechSynthesis?.cancel?.();
    setLoading(true);
    setError('');
    setLesson(null);
    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topic.trim(), script: script.trim() })
      });
      const raw = await response.text();
      let data;
      try { data = JSON.parse(raw); }
      catch { throw new Error(raw || 'The server returned an unreadable response.'); }
      if (!response.ok) {
        const detail = data?.detail;
        throw new Error(typeof detail === 'string' ? detail : `Request failed (${response.status}).`);
      }
      if (!data || !Array.isArray(data.sections) || data.sections.length === 0) {
        throw new Error('The response did not contain any lesson sections. Please try again.');
      }
      setLesson(data);
      setActiveIndex(0);
    } catch (err) {
      setError(`${err.message} Make sure the backend is running at http://127.0.0.1:8000.`);
    } finally {
      setLoading(false);
    }
  }

  function speak() {
    if (!activeSection?.narration) return;
    if (!('speechSynthesis' in window)) {
      setError('Text-to-speech is not supported in this browser. Try Chrome or Edge.');
      return;
    }
    if (window.speechSynthesis.speaking && window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setSpeaking(true);
      setPaused(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(activeSection.narration);
    if (selectedVoice) utterance.voice = selectedVoice;
    utterance.rate = Number(rate);
    utterance.onstart = () => { setSpeaking(true); setPaused(false); };
    utterance.onend = () => { setSpeaking(false); setPaused(false); };
    utterance.onerror = () => { setSpeaking(false); setPaused(false); };
    window.speechSynthesis.speak(utterance);
  }

  function pauseSpeech() {
    if (!window.speechSynthesis) return;
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      window.speechSynthesis.pause();
      setPaused(true);
    } else if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
      setPaused(false);
    }
  }

  function saveLesson() {
    if (!lesson) return;
    const fileContent = JSON.stringify(lesson, null, 2);
    const blob = new Blob([fileContent], { type: 'application/json' });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeName = (lesson.title || lesson.topic || 'lesson')
      .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    link.href = downloadUrl;
    link.download = `${safeName || 'lesson'}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
  }

  async function loadLessonFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const valid = data && typeof data.title === 'string'
        && typeof data.topic === 'string' && typeof data.introduction === 'string'
        && Array.isArray(data.sections) && data.sections.length >= 1
        && data.sections.every((section) => typeof section.heading === 'string'
          && typeof section.narration === 'string'
          && section.slide && typeof section.slide.title === 'string'
          && Array.isArray(section.slide.bullet_points));
      if (!valid) throw new Error('This file is not a valid LessonForge lesson.');
      window.speechSynthesis?.cancel?.();
      setSpeaking(false);
      setPaused(false);
      setLesson(data);
      setActiveIndex(0);
      setError('');
    } catch (err) {
      setError(err instanceof SyntaxError
        ? 'The selected file is not valid JSON.'
        : (err.message || 'Could not load this lesson file.'));
    } finally {
      event.target.value = '';
    }
  }

  function changeSection(next) {
    if (next < 0 || next >= sections.length) return;
    window.speechSynthesis?.cancel?.();
    setSpeaking(false);
    setPaused(false);
    setActiveIndex(next);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="AI Lesson Generator home">
          <span className="brand-mark"><GraduationCap size={22} /></span>
          <span>Lesson<span className="brand-accent">Forge</span></span>
        </a>
        <div className="topbar-actions">
          <input ref={fileInputRef} className="file-input-hidden" type="file" accept=".json,application/json" onChange={loadLessonFile} />
          <button className="topbar-action" onClick={() => fileInputRef.current?.click()}><Upload size={15} /> Load lesson</button>
          {lesson && <button className="topbar-action save-action" onClick={saveLesson}><Download size={15} /> Save lesson</button>}
          <div className="topbar-note"><span className="status-dot" /> AI-powered learning studio</div>
        </div>
      </header>

      <main className="main-wrap">
        {!lesson && (
          <section className="hero">
            <div className="eyebrow"><Sparkles size={14} /> YOUR PERSONAL LEARNING STUDIO</div>
            <h1>Turn any topic into<br /><span>a lesson worth learning.</span></h1>
            <p className="hero-copy">Create a structured lesson with clear explanations, presentation slides and spoken narration.</p>
            <form className="generator-card" onSubmit={generateLesson}>
              <label htmlFor="topic">What do you want to learn?</label>
              <input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. How artificial intelligence works" />
              <label htmlFor="script" className="optional-label">Lecturer notes or outline <span>OPTIONAL</span></label>
              <textarea id="script" value={script} onChange={(e) => setScript(e.target.value)}
                placeholder="Paste your lecturer's notes or lesson outline here..." rows="4" />
              {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}
              <button className="generate-button" type="submit" disabled={loading}>
                {loading ? <><LoaderCircle className="spin" size={18} /> Creating your lesson...</> : <><Sparkles size={18} /> Generate lesson</>}
              </button>
              <div className="form-foot"><BookOpen size={14} /> Your lesson will include explanations, slides and sources.</div>
            </form>
          </section>
        )}

        {lesson && (
          <>
            <div className="lesson-heading">
              <button className="back-button" onClick={() => { window.speechSynthesis?.cancel?.(); setLesson(null); setError(''); }}>← New lesson</button>
              <div className="eyebrow"><Sparkles size={14} /> YOUR GENERATED LESSON</div>
              <h1>{lesson.title || lesson.topic}</h1>
              <p>{lesson.introduction}</p>
              <div className="lesson-meta"><span><BookOpen size={15} /> {sections.length} sections</span><span><Clock3 size={15} /> Learn at your own pace</span></div>
            </div>

            <div className="player-layout">
              <aside className="section-sidebar">
                <div className="sidebar-title">LESSON CONTENT <span>{String(sections.length).padStart(2, '0')}</span></div>
                <div className="section-list">
                  {sections.map((section, index) => (
                    <button key={`${section.heading}-${index}`}
                      className={`section-item ${index === activeIndex ? 'selected' : ''}`}
                      onClick={() => changeSection(index)}>
                      <span className="section-number">{String(index + 1).padStart(2, '0')}</span>
                      <span>{section.heading}</span>
                    </button>
                  ))}
                </div>
                <div className="progress-area"><div className="progress-label"><span>YOUR PROGRESS</span><strong>{Math.round(progress)}%</strong></div><div className="progress-track"><div style={{ width: `${progress}%` }} /></div></div>
              </aside>

              <section className="lesson-main">
                {activeSection && (
                  <>
                    <div className="section-kicker">SECTION {String(activeIndex + 1).padStart(2, '0')} OF {String(sections.length).padStart(2, '0')}</div>
                    <h2>{activeSection.heading}</h2>
                    <div className="slide-card">
                      <div className="slide-top"><span className="slide-label">PRESENTATION SLIDE</span><span className="slide-counter">{activeIndex + 1} / {sections.length}</span></div>
                      <h3>{activeSection.slide?.title || activeSection.heading}</h3>
                      <ul>
                        {(activeSection.slide?.bullet_points || []).map((point, index) => <li key={index}>{point}</li>)}
                      </ul>
                      <div className="slide-footer">LESSONFORGE <span>•</span> {lesson.topic || 'Learning session'}</div>
                    </div>

                    <div className="narration-card">
                      <div className={`avatar-stage ${speaking && !paused ? 'avatar-speaking' : ''} ${paused ? 'avatar-paused' : ''}`}>
                        <div className="avatar-glow" />
                        <div className="avatar-robot">
                          <div className="avatar-antenna" />
                          <div className="avatar-face">
                            <span className="avatar-eye" /><span className="avatar-eye" />
                            <span className="avatar-mouth" />
                          </div>
                        </div>
                        <div className="avatar-caption"><Bot size={13} /> {speaking && !paused ? 'Your AI tutor is speaking' : paused ? 'Your AI tutor is paused' : 'Your AI tutor is ready'}</div>
                      </div>
                      <div className="narration-title"><Volume2 size={17} /> LESSON NARRATION</div>
                      <p className="transcript">{activeSection.narration}</p>
                      <div className="audio-controls">
                        <button className="control-button secondary" onClick={() => changeSection(activeIndex - 1)} disabled={activeIndex === 0} aria-label="Previous section"><SkipBack size={18} /></button>
                        <button className="control-button play-button" onClick={speaking && !paused ? pauseSpeech : speak} aria-label={speaking && !paused ? 'Pause narration' : 'Play narration'}>
                          {speaking && !paused ? <Pause size={19} /> : <Play size={19} fill="currentColor" />}
                        </button>
                        <button className="control-button secondary" onClick={() => changeSection(activeIndex + 1)} disabled={activeIndex === sections.length - 1} aria-label="Next section"><SkipForward size={18} /></button>
                        <div className="audio-settings">
                          <label>VOICE<select value={voiceName} onChange={(e) => setVoiceName(e.target.value)}><option value="">Default voice</option>{voices.map((voice) => <option key={voice.name} value={voice.name}>{voice.name} ({voice.lang})</option>)}</select></label>
                          <label>SPEED<select value={rate} onChange={(e) => setRate(Number(e.target.value))}><option value="0.75">0.75×</option><option value="1">1× Normal</option><option value="1.25">1.25×</option><option value="1.5">1.5×</option><option value="1.75">1.75×</option></select></label>
                        </div>
                      </div>
                      {paused && <div className="paused-note">Narration paused — press play to continue.</div>}
                    </div>

                    <div className="bottom-navigation">
                      <button onClick={() => changeSection(activeIndex - 1)} disabled={activeIndex === 0}>← Previous section</button>
                      <button className="next-button" onClick={() => changeSection(activeIndex + 1)} disabled={activeIndex === sections.length - 1}>Next section →</button>
                    </div>
                  </>
                )}
                {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}
              </section>
            </div>

            {Array.isArray(lesson.sources) && lesson.sources.length > 0 && (
              <section className="sources-card">
                <div><div className="section-kicker">FURTHER READING</div><h3>Sources used for this lesson</h3></div>
                <div className="source-list">{lesson.sources.map((source, index) => <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer"><span>{source.title}</span><ExternalLink size={15} /></a>)}</div>
              </section>
            )}
          </>
        )}
      </main>
      <footer className="footer">LESSONFORGE <span>•</span> AI LESSON GENERATOR</footer>
    </div>
  );
}