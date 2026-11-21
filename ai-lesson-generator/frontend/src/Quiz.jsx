import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Check, ChevronLeft, ChevronRight, LoaderCircle, RefreshCw, Shuffle, Trophy, X } from 'lucide-react';
import { api } from './api';
import { getProgress, recordFinalScore, recordSectionScore } from './progress';

function QuestionRunner({ title, questions, onFinish, onExit }) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState(null);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);
  const q = questions[index];

  function choose(option) {
    if (picked !== null) return;
    setPicked(option);
    if (option === q.answer_index) setScore((s) => s + 1);
  }
  function next() {
    if (index + 1 < questions.length) { setIndex(index + 1); setPicked(null); } else { setDone(true); onFinish(score); }
  }

  if (done) {
    const pct = Math.round((score / questions.length) * 100);
    return (
      <div className="quiz-card quiz-result">
        <Trophy size={34} />
        <h3>{pct >= 80 ? 'Excellent work!' : pct >= 50 ? 'Good effort!' : 'Keep going!'}</h3>
        <p className="quiz-score">{score} / {questions.length} correct ({pct}%)</p>
        <p className="quiz-hint">{pct >= 80 ? 'You have clearly understood this. Move on to the next section.' : 'Replay the lecture section, ask the lecturer about anything unclear, then try again.'}</p>
        <div className="quiz-actions"><button onClick={() => { setIndex(0); setPicked(null); setScore(0); setDone(false); }}>Try again</button><button className="primary" onClick={onExit}>Back to quizzes</button></div>
      </div>
    );
  }
  return (
    <div className="quiz-card">
      <div className="quiz-top"><span>{title}</span><span>Question {index + 1} of {questions.length}</span></div>
      <div className="progress-track small"><div style={{ width: `${((index + (picked !== null ? 1 : 0)) / questions.length) * 100}%` }} /></div>
      <h3>{q.question}</h3>
      <div className="quiz-options">
        {q.options.map((option, i) => {
          const state = picked === null ? '' : i === q.answer_index ? 'right' : picked === i ? 'wrong' : 'dim';
          return (
            <button key={i} className={`quiz-option ${state}`} onClick={() => choose(i)} disabled={picked !== null}>
              <span className="quiz-letter">{String.fromCharCode(65 + i)}</span><span>{option}</span>
              {state === 'right' && <Check size={17} />}{state === 'wrong' && <X size={17} />}
            </button>
          );
        })}
      </div>
      {picked !== null && (
        <div className={`quiz-feedback ${picked === q.answer_index ? 'right' : 'wrong'}`}>
          <b>{picked === q.answer_index ? 'Correct!' : 'Not quite.'}</b> {q.explanation}
          <button className="primary" onClick={next}>{index + 1 < questions.length ? 'Next question' : 'See my score'}</button>
        </div>
      )}
    </div>
  );
}

function Flashcards({ cards }) {
  const [order, setOrder] = useState(() => cards.map((_, i) => i));
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const card = cards[order[pos]];
  const go = (d) => { setFlipped(false); setPos((p) => (p + d + order.length) % order.length); };
  useEffect(() => {
    const key = (e) => { if (e.key === 'ArrowRight') go(1); else if (e.key === 'ArrowLeft') go(-1); else if (e.key === ' ') { e.preventDefault(); setFlipped((f) => !f); } };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  });
  if (!card) return <p className="quiz-hint">No flashcards yet.</p>;
  return (
    <div className="flash-wrap">
      <button className={`flashcard ${flipped ? 'flipped' : ''}`} onClick={() => setFlipped((f) => !f)} aria-label="Flip card">
        <div className="flash-inner">
          <div className="flash-face front"><small>QUESTION</small><p>{card.front}</p><em>Click or press space to reveal</em></div>
          <div className="flash-face back"><small>ANSWER</small><p>{card.back}</p></div>
        </div>
      </button>
      <div className="flash-controls">
        <button onClick={() => go(-1)} aria-label="Previous card"><ChevronLeft size={18} /></button>
        <span>{pos + 1} / {order.length}</span>
        <button onClick={() => go(1)} aria-label="Next card"><ChevronRight size={18} /></button>
        <button onClick={() => { setOrder((o) => [...o].sort(() => Math.random() - 0.5)); setPos(0); setFlipped(false); }}><Shuffle size={15} /> Shuffle</button>
      </div>
    </div>
  );
}

export default function QuizPanel({ lesson, ensureSaved, mode, bump }) {
  const [quiz, setQuiz] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [run, setRun] = useState(null);
  const lessonId = lesson.id;
  const progress = useMemo(() => getProgress(lessonId), [lessonId, run, bump]);

  useEffect(() => {
    setQuiz(null); setRun(null); setError('');
    if (lessonId) api.getQuiz(lessonId).then(setQuiz).catch(() => {});
  }, [lessonId]);

  async function create(force = false) {
    setLoading(true); setError('');
    try {
      const id = await ensureSaved();
      setQuiz(await (force ? api.newQuiz(id) : api.quiz(id)));
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  }

  if (!quiz) {
    return (
      <div className="quiz-card quiz-empty">
        <Trophy size={30} />
        <h3>{mode === 'flashcards' ? 'Flashcards' : 'Test yourself'}</h3>
        <p className="quiz-hint">The AI writes a quiz for every section, a final test and flashcards from this lesson. It takes about 20 seconds, then it is saved.</p>
        {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}
        <button className="primary" onClick={() => create()} disabled={loading}>{loading ? <><LoaderCircle className="spin" size={16} /> Writing questions…</> : 'Create quiz & flashcards'}</button>
      </div>
    );
  }

  if (mode === 'flashcards') return <Flashcards cards={quiz.flashcards || []} />;

  if (run) return <QuestionRunner {...run} onExit={() => setRun(null)} />;

  const sectionQuiz = (i) => quiz.sections.find((s) => s.section_index === i);
  return (
    <div className="quiz-list">
      {lesson.sections.map((section, i) => {
        const sq = sectionQuiz(i);
        const best = progress.sections[i];
        return (
          <div key={i} className="quiz-row">
            <span className="section-number">{String(i + 1).padStart(2, '0')}</span>
            <div><b>{section.heading}</b><small>{sq ? `${sq.questions.length} questions` : 'No questions generated'}{best ? ` · best ${best.best}/${best.total}` : ''}</small></div>
            <button disabled={!sq} onClick={() => setRun({ title: section.heading, questions: sq.questions, onFinish: (score) => recordSectionScore(lessonId, i, score, sq.questions.length) })}>{best ? 'Retake' : 'Start'}</button>
          </div>
        );
      })}
      {quiz.final?.length > 0 && (
        <div className="quiz-row final">
          <span className="section-number"><Trophy size={15} /></span>
          <div><b>Final test</b><small>{quiz.final.length} questions across the whole lesson{progress.final ? ` · best ${progress.final.best}/${progress.final.total}` : ''}</small></div>
          <button className="primary" onClick={() => setRun({ title: 'Final test', questions: quiz.final, onFinish: (score) => recordFinalScore(lessonId, score, quiz.final.length) })}>{progress.final ? 'Retake' : 'Start'}</button>
        </div>
      )}
      <button className="quiz-regen" onClick={() => create(true)} disabled={loading}>{loading ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />} Write new questions</button>
      {error && <div className="error-message"><AlertCircle size={17} />{error}</div>}
    </div>
  );
}
