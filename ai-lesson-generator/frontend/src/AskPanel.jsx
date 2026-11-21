import { useRef, useState } from 'react';
import { LoaderCircle, Mic, Send } from 'lucide-react';
import { LANG_TAG } from './lecturers';

/** "Ask the lecturer": type or speak a question; the lecturer answers at the board. */
export default function AskPanel({ language, busy, onAsk, history, disabled }) {
  const [question, setQuestion] = useState('');
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef(null);
  const Recognition = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;

  function submit(event) {
    event?.preventDefault();
    const text = question.trim();
    if (text.length < 3 || busy) return;
    setQuestion('');
    onAsk(text);
  }

  function listen() {
    if (!Recognition) return;
    if (listening) { recognitionRef.current?.stop(); return; }
    const rec = new Recognition();
    rec.lang = LANG_TAG[language] || 'en-US';
    rec.interimResults = false;
    rec.onresult = (e) => setQuestion(e.results[0][0].transcript);
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
  }

  return (
    <div className="ask-panel no-print">
      <div className="narration-title">ASK THE LECTURER <span className="narration-hint">Stuck? Interrupt, like in a real class.</span></div>
      <form className="ask-form" onSubmit={submit}>
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="e.g. Can you explain that last part with an example?" maxLength={500} disabled={disabled} />
        {Recognition && <button type="button" className={`ask-mic ${listening ? 'on' : ''}`} onClick={listen} aria-label="Ask by voice" title="Ask by voice"><Mic size={17} /></button>}
        <button type="submit" className="ask-send" disabled={busy || question.trim().length < 3 || disabled}>{busy ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />} Ask</button>
      </form>
      {history.length > 0 && (
        <ul className="ask-history">
          {history.slice(-3).map((h, i) => <li key={i}><b>You:</b> {h.q}</li>)}
        </ul>
      )}
    </div>
  );
}
