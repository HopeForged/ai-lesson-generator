import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle, BookOpen, Clock3, Download, ExternalLink, Film, Layers, Link2, NotebookText, Pause, Play,
  Sparkles, SkipBack, SkipForward, Trophy, Volume2, Undo2, LoaderCircle,
} from 'lucide-react';
import VisualScene from './VisualScene';
import TutorAvatar from './TutorAvatar';
import AskPanel from './AskPanel';
import QuizPanel from './Quiz';
import StudyNotes from './StudyNotes';
import VideoPanel from './VideoPanel';
import { usePlayer } from './usePlayer';
import { buildBeats, splitSentences } from './lectureUtils';
import { LECTURERS, loadSetting, saveSetting } from './lecturers';
import { api } from './api';
import { getProgress, markVisited } from './progress';

function pickDefaultVoice(list, tag) {
  const same = list.filter((v) => v.lang?.toLowerCase().startsWith((tag || 'en').slice(0, 2).toLowerCase()));
  const pool = same.length ? same : list;
  for (const rule of [/natural|neural|online/i, /google|samantha|daniel|karen|moira|serena|aria|jenny|guy/i, /./]) {
    const hit = pool.find((v) => rule.test(v.name));
    if (hit) return hit;
  }
  return list[0];
}

export default function LessonView({ initialLesson, onBack, caps }) {
  const [lesson, setLesson] = useState(initialLesson);
  const [tab, setTab] = useState('lecture');
  const [panel, setPanel] = useState(null);           // null | 'video'
  const [activeIndex, setActiveIndex] = useState(0);
  const [voices, setVoices] = useState([]);
  const [voiceName, setVoiceName] = useState('');
  const [rate, setRate] = useState(() => loadSetting('rate', 1));
  const [lecturer, setLecturer] = useState(() => loadSetting('lecturer', 'mensah'));
  const [autoNext, setAutoNext] = useState(true);
  const [override, setOverride] = useState(null);     // an answer to a student question: {question, beat}
  const [asking, setAsking] = useState(false);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [progressTick, setProgressTick] = useState(0);
  const autoStartRef = useRef(false);

  const sections = lesson.sections;
  const activeSection = sections[activeIndex];
  const sectionBeats = useMemo(() => buildBeats(activeSection), [activeSection]);
  const beats = override ? [override.beat] : sectionBeats;
  const live = useRef({});
  live.current = { autoNext, activeIndex, count: sections.length, override };

  const player = usePlayer({
    beats, language: lesson.language || 'English', lecturer, rate, voiceName, voices,
    onFinish: (tk) => {
      const { autoNext: auto, activeIndex: index, count, override: ov } = live.current;
      if (ov || !auto || index + 1 >= count) return;
      window.setTimeout(() => { autoStartRef.current = true; setActiveIndex(index + 1); }, 1200);
    },
  });
  const safeBeat = Math.min(player.beatIndex, Math.max(0, beats.length - 1));
  const activeBeat = beats[safeBeat];
  const progress = getProgress(lesson.id);
  const visitedCount = Math.max(progress.visited.length, activeIndex + 1) ;
  const percent = Math.min(100, Math.round((visitedCount / sections.length) * 100));

  useEffect(() => {
    const load = () => {
      const available = window.speechSynthesis?.getVoices?.() ?? [];
      setVoices(available);
      setVoiceName((cur) => cur || (available.length ? pickDefaultVoice(available, lesson.language).name : ''));
    };
    load();
    window.speechSynthesis?.addEventListener?.('voiceschanged', load);
    return () => window.speechSynthesis?.removeEventListener?.('voiceschanged', load);
  }, [lesson.language]);

  // New section: start from its first diagram (and continue the lecture automatically if it was playing).
  useEffect(() => {
    player.reset();
    setOverride(null);
    markVisited(lesson.id, activeIndex);
    setProgressTick((n) => n + 1);
    let starter = null;
    if (autoStartRef.current) { autoStartRef.current = false; starter = window.setTimeout(() => player.playFrom(0), 500); }
    return () => { if (starter) window.clearTimeout(starter); };
  }, [activeIndex]); // eslint-disable-line

  // Warm up the next section's voice so there is no pause between sections.
  useEffect(() => {
    const next = sections[activeIndex + 1];
    if (next) player.prefetch(buildBeats(next));
  }, [activeIndex, lecturer, rate]); // eslint-disable-line

  // An answer to a question starts playing as soon as it is on the board.
  useEffect(() => { if (override) player.playFrom(0); }, [override]); // eslint-disable-line

  function changeSection(next) {
    if (next < 0 || next >= sections.length) return;
    autoStartRef.current = false;
    player.stop();
    setOverride(null);
    setActiveIndex(next);
  }

  async function ensureSaved() {
    if (lesson.id) return lesson.id;
    const { id } = await api.saveToLibrary(lesson);
    setLesson((l) => ({ ...l, id }));
    return id;
  }

  async function ask(question) {
    setAsking(true); setError('');
    try {
      const res = await api.ask({ lesson, section_index: activeIndex, question, history });
      const text = res.say;
      const beat = { text, start: 0, end: text.length, cue_text: splitSentences(text)[0] || text, scene: res.scene, avatar_action: res.avatar_action };
      setHistory((h) => [...h, { q: question, a: text }]);
      player.stop();
      setOverride({ question, beat });
    } catch (err) { setError(err.message); } finally { setAsking(false); }
  }

  function backToLesson() { player.stop(); setOverride(null); }

  function saveJson() {
    const blob = new Blob([JSON.stringify(lesson, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${(lesson.title || 'lesson').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'lesson'}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copyLink() {
    try {
      const id = await ensureSaved();
      await navigator.clipboard.writeText(`${window.location.origin}/#/lesson/${id}`);
      setCopied(true); setTimeout(() => setCopied(false), 2000);
    } catch (err) { setError(err.message || 'Could not copy the link.'); }
  }

  function renderBeatText(beat, index) {
    const isActive = index === safeBeat;
    let body = beat.text;
    if (isActive && player.speaking && player.beatPos >= 0) {
      const word = beat.text.slice(player.beatPos).match(/^\S+/)?.[0] || '';
      body = <>{beat.text.slice(0, player.beatPos)}<mark className="spoken-highlight">{word}</mark>{beat.text.slice(player.beatPos + word.length)}</>;
    }
    return <span key={index} className={`beat-text ${isActive ? 'is-active' : ''} ${index < safeBeat ? 'is-done' : ''}`} onClick={() => player.pickBeat(index)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') player.pickBeat(index); }}>{body}{' '}</span>;
  }

  const currentSentence = (() => {
    if (!activeBeat || !player.speaking) return '';
    let offset = 0;
    for (const sentence of splitSentences(activeBeat.text)) {
      const at = activeBeat.text.indexOf(sentence, offset);
      offset = at + sentence.length;
      if (player.beatPos < offset) return sentence;
    }
    return '';
  })();

  const tabs = [['lecture', 'Lecture', Volume2], ['quiz', 'Quizzes', Trophy], ['flashcards', 'Flashcards', Layers], ['notes', 'Study notes', NotebookText]];

  return (
    <>
      <div className="lesson-heading no-print">
        <button className="back-button" onClick={() => { player.stop(); onBack(); }}>← Library</button>
        <div className="eyebrow"><Sparkles size={14} /> YOUR LESSON</div>
        <h1>{lesson.title || lesson.topic}</h1>
        <p>{lesson.introduction}</p>
        <div className="lesson-meta">
          <span><BookOpen size={15} /> {sections.length} sections</span>
          <span><Clock3 size={15} /> {lesson.language || 'English'} · {lesson.level || 'intermediate'}</span>
          {lesson.quality_review && <span title={(lesson.quality_review.issues || []).join('\n')}><Sparkles size={15} /> Quality checked: {lesson.quality_review.score}/100{lesson.quality_review.passed ? ' ✓' : ' – review advised'}</span>}
        </div>
        <div className="export-row">
          <button onClick={() => setPanel(panel === 'video' ? null : 'video')} className={panel === 'video' ? 'on' : ''}><Film size={15} /> Make video</button>
          <button onClick={() => setTab('notes')}><NotebookText size={15} /> Study notes / PDF</button>
          <button onClick={saveJson}><Download size={15} /> Save file</button>
          <button onClick={copyLink}><Link2 size={15} /> {copied ? 'Link copied!' : 'Copy link'}</button>
        </div>
        {panel === 'video' && <VideoPanel lesson={lesson} lecturer={lecturer} rate={rate} caps={caps} ensureSaved={ensureSaved} />}
      </div>

      <div className="tabs no-print" role="tablist">
        {tabs.map(([id, label, Icon]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'on' : ''} onClick={() => { setTab(id); if (id !== 'lecture') player.stop(); }}><Icon size={15} /> {label}</button>)}
      </div>

      {tab === 'notes' && <StudyNotes lesson={lesson} />}
      {(tab === 'quiz' || tab === 'flashcards') && <div className="quiz-wrap"><QuizPanel lesson={lesson} ensureSaved={ensureSaved} mode={tab} bump={progressTick} /></div>}

      {tab === 'lecture' && (
        <div className="player-layout">
          <aside className="section-sidebar">
            <div className="sidebar-title">LESSON CONTENT <span>{String(sections.length).padStart(2, '0')}</span></div>
            <div className="section-list">
              {sections.map((section, index) => (
                <button key={`${section.heading}-${index}`} className={`section-item ${index === activeIndex ? 'selected' : ''} ${progress.visited.includes(index) && index !== activeIndex ? 'visited' : ''}`} onClick={() => changeSection(index)}>
                  <span className="section-number">{String(index + 1).padStart(2, '0')}</span>
                  <span>{section.heading}</span>
                </button>
              ))}
            </div>
            <div className="progress-area"><div className="progress-label"><span>YOUR PROGRESS</span><strong>{percent}%</strong></div><div className="progress-track"><div style={{ width: `${percent}%` }} /></div></div>
          </aside>

          <section className="lesson-main">
            <div className="section-kicker">SECTION {String(activeIndex + 1).padStart(2, '0')} OF {String(sections.length).padStart(2, '0')}</div>
            <h2>{activeSection.heading}</h2>

            {override && (
              <div className="question-banner">
                <span><b>Your question:</b> {override.question}</span>
                <button onClick={backToLesson}><Undo2 size={14} /> Back to the lesson</button>
              </div>
            )}

            <div className="stage">
              <div className="stage-board">
                <VisualScene
                  key={`${override ? 'q' : activeIndex}-${safeBeat}-${override?.question || ''}`}
                  scene={activeBeat?.scene || activeSection.visual_scene}
                  beatText={activeBeat?.text || ''}
                  beatPos={player.beatPos}
                  playing={player.speaking && !player.preparing}
                  paused={player.paused}
                  beatNumber={safeBeat + 1}
                  beatCount={beats.length}
                  sectionIndex={activeIndex}
                  onPickBeat={player.pickBeat}
                />
                <div className={`subtitle ${currentSentence ? 'on' : ''}`} aria-live="polite">{player.preparing ? 'The lecturer is getting ready…' : (currentSentence || ' ')}</div>
              </div>
              <div className="stage-lecturer">
                <TutorAvatar speaking={player.speaking && !player.preparing} paused={player.paused} action={activeBeat?.avatar_action || 'explain'} look={lecturer} mouth={player.voiceMode === 'server' && player.speaking ? (player.mouth ?? 0) : null} />
              </div>
            </div>

            <div className="narration-card">
              <div className="narration-title"><Volume2 size={17} /> LECTURE SCRIPT <span className="narration-hint">{player.voiceMode === 'server' ? 'Natural voice' : player.voiceMode === 'browser' ? 'Browser voice' : 'Click any passage to jump to it'}</span></div>
              <p className="transcript">{beats.map(renderBeatText)}</p>
              <div className="audio-controls">
                <button className="control-button secondary" onClick={() => changeSection(activeIndex - 1)} disabled={activeIndex === 0} aria-label="Previous section"><SkipBack size={18} /></button>
                <button className="control-button play-button" onClick={player.togglePlay} aria-label={player.speaking && !player.paused ? 'Pause lecture' : 'Play lecture'}>
                  {player.preparing ? <LoaderCircle className="spin" size={19} /> : player.speaking && !player.paused ? <Pause size={19} /> : <Play size={19} fill="currentColor" />}
                </button>
                <button className="control-button secondary" onClick={() => changeSection(activeIndex + 1)} disabled={activeIndex === sections.length - 1} aria-label="Next section"><SkipForward size={18} /></button>
                <div className="audio-settings">
                  <label>LECTURER<select value={lecturer} onChange={(e) => { setLecturer(e.target.value); saveSetting('lecturer', e.target.value); player.stop(); }}>{LECTURERS.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
                  {player.voiceMode === 'browser' && <label>VOICE<select value={voiceName} onChange={(e) => setVoiceName(e.target.value)}><option value="">Default voice</option>{voices.map((voice) => <option key={voice.name} value={voice.name}>{voice.name} ({voice.lang})</option>)}</select></label>}
                  <label>SPEED<select value={rate} onChange={(e) => { setRate(Number(e.target.value)); saveSetting('rate', Number(e.target.value)); player.stop(); }}><option value="0.8">0.8×</option><option value="0.9">0.9×</option><option value="1">1× Normal</option><option value="1.15">1.15×</option><option value="1.3">1.3×</option></select></label>
                  <label className="auto-toggle"><span>AUTO-CONTINUE</span><button type="button" role="switch" aria-checked={autoNext} className={autoNext ? 'on' : ''} onClick={() => setAutoNext((v) => !v)}><i /></button></label>
                </div>
              </div>
              {player.paused && <div className="paused-note">Lecture paused — press play to continue.</div>}
              {caps && !caps.voice && player.voiceMode !== 'server' && <div className="voice-tip">Tip: for a much more natural voice, run <code>pip install edge-tts</code> in the backend (free, no key) and restart it.</div>}
            </div>

            <AskPanel language={lesson.language || 'English'} busy={asking} onAsk={ask} history={history} />
            {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}

            <div className="slide-card">
              <div className="slide-top"><span className="slide-label">PRESENTATION NOTES</span><span className="slide-counter">{activeIndex + 1} / {sections.length}</span></div>
              <h3>{activeSection.slide?.title || activeSection.heading}</h3>
              <ul>{(activeSection.slide?.bullet_points || []).map((point, index) => <li key={index}>{point}</li>)}</ul>
              <div className="slide-footer">LESSONFORGE <span>•</span> {lesson.topic || 'Learning session'}</div>
            </div>

            <div className="bottom-navigation">
              <button onClick={() => changeSection(activeIndex - 1)} disabled={activeIndex === 0}>← Previous section</button>
              {activeIndex === sections.length - 1
                ? <button className="next-button" onClick={() => setTab('quiz')}>Test yourself →</button>
                : <button className="next-button" onClick={() => changeSection(activeIndex + 1)}>Next section →</button>}
            </div>
          </section>
        </div>
      )}

      {Array.isArray(lesson.sources) && lesson.sources.length > 0 && tab !== 'notes' && (
        <section className="sources-card no-print">
          <div><div className="section-kicker">FURTHER READING</div><h3>Sources used for this lesson</h3></div>
          <div className="source-list">{lesson.sources.map((source, index) => <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer"><span>{source.title}</span><ExternalLink size={15} /></a>)}</div>
        </section>
      )}
    </>
  );
}
