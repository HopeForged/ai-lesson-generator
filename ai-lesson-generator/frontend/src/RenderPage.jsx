import { useEffect, useRef, useState } from 'react';
import VisualScene from './VisualScene';
import TutorAvatar from './TutorAvatar';
import { charAtTime, mouthAtTime, splitSentences } from './lectureUtils';
import './render.css';

/**
 * The page that headless Chromium records to make the MP4. It plays a timeline built by the backend
 * (exact audio timings) with a clock, so the picture is always in step with the narration track.
 * It exposes: window.__videoReady, window.__startTimeline(), window.__videoDone.
 */
export default function RenderPage({ videoId }) {
  const [timeline, setTimeline] = useState(null);
  const [t, setT] = useState(-1);
  const startRef = useRef(null);

  useEffect(() => {
    window.__videoReady = false; window.__videoDone = false; window.__videoError = '';
    fetch(`/api/video/jobs/${videoId}/timeline`)
      .then((r) => { if (!r.ok) throw new Error(`timeline ${r.status}`); return r.json(); })
      .then(async (data) => {
        try { await document.fonts?.ready; } catch { /* ignore */ }
        setTimeline(data);
        setT(0);
        window.__startTimeline = () => {
          startRef.current = performance.now();
          const tick = () => {
            const now = (performance.now() - startRef.current) / 1000;
            if (now >= data.total) { setT(data.total - 0.001); window.__videoDone = true; return; }
            setT(now);
            window.requestAnimationFrame(tick);
          };
          window.requestAnimationFrame(tick);
          return Date.now();
        };
        window.setTimeout(() => { window.__videoReady = true; }, 300);
      })
      .catch((err) => { window.__videoError = String(err.message || err); });
  }, [videoId]);

  if (!timeline) return <div className="video-root" />;
  const seg = timeline.segments.find((s) => t >= s.start && t < s.end) || timeline.segments[timeline.segments.length - 1];
  const lessonInfo = timeline.lesson;
  const look = timeline.lecturer || 'mensah';
  const names = { mensah: 'Dr. Mensah', naledi: 'Prof. Naledi', walker: 'Mr. Walker' };
  const local = t - seg.start;
  const fade = Math.min(1, local / 0.6, (seg.end - t) / 0.6);

  let body = null;
  if (seg.type === 'title') {
    body = (
      <div className="video-card" style={{ opacity: Math.max(0, fade) }}>
        <div className="vc-brand">LESSONFORGE</div>
        <h1>{lessonInfo.title}</h1>
        <p>{lessonInfo.introduction}</p>
        <div className="vc-who">Presented by {names[look] || 'your lecturer'}</div>
      </div>
    );
  } else if (seg.type === 'section') {
    body = (
      <div className="video-card" style={{ opacity: Math.max(0, fade) }}>
        <div className="vc-brand">SECTION {seg.section + 1} OF {lessonInfo.sections.length}</div>
        <h1>{lessonInfo.sections[seg.section].heading}</h1>
      </div>
    );
  } else if (seg.type === 'outro') {
    body = (
      <div className="video-card" style={{ opacity: Math.max(0, fade) }}>
        <div className="vc-brand">THANK YOU FOR WATCHING</div>
        <h1>{lessonInfo.title}</h1>
        <p>Made with LessonForge</p>
      </div>
    );
  } else {
    const speaking = local < seg.speech_end - seg.start;
    const pos = charAtTime(seg.words, local);
    let sentence = '';
    let offset = 0;
    for (const s of splitSentences(seg.text)) {
      const at = seg.text.indexOf(s, offset);
      offset = at + s.length;
      if (pos < offset) { sentence = s; break; }
    }
    const beatCount = timeline.segments.filter((x) => x.type === 'beat' && x.section === seg.section).length;
    body = (
      <div className="video-stage">
        <div className="vs-top"><span>{lessonInfo.title}</span><span>Section {seg.section + 1} · {lessonInfo.sections[seg.section].heading}</span></div>
        <div className="vs-main">
          <div className="vs-board">
            <VisualScene key={`${seg.section}-${seg.beat}`} compact scene={seg.scene} beatText={seg.text} beatPos={pos} playing={speaking} paused={false}
              beatNumber={seg.beat + 1} beatCount={beatCount} sectionIndex={seg.section} />
          </div>
          <div className="vs-lecturer">
            <TutorAvatar speaking={speaking} paused={false} action={seg.avatar_action} look={look} mouth={speaking ? mouthAtTime(seg.words, local) : 0} caption={names[look]} />
          </div>
        </div>
        <div className="vs-subtitle">{sentence}</div>
      </div>
    );
  }
  return (
    <div className="video-root">
      {body}
      <div className="vs-progress"><div style={{ width: `${(t / timeline.total) * 100}%` }} /></div>
    </div>
  );
}
