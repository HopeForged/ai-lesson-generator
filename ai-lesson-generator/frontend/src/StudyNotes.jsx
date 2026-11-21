import { Download, Printer } from 'lucide-react';

export function notesMarkdown(lesson) {
  const lines = [`# ${lesson.title}`, '', lesson.introduction, ''];
  lesson.sections.forEach((s, i) => {
    lines.push(`## ${i + 1}. ${s.heading}`, '');
    (s.slide?.bullet_points || []).forEach((b) => lines.push(`- ${b}`));
    lines.push('', s.narration, '');
  });
  if (lesson.sources?.length) { lines.push('## Sources', ''); lesson.sources.forEach((s) => lines.push(`- [${s.title}](${s.url})`)); }
  return lines.join('\n');
}

export function downloadText(name, text, type = 'text/markdown') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement('a');
  a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function StudyNotes({ lesson }) {
  const slug = (lesson.title || 'lesson').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return (
    <div className="notes-wrap">
      <div className="notes-actions no-print">
        <button className="primary" onClick={() => window.print()}><Printer size={15} /> Print / save as PDF</button>
        <button onClick={() => downloadText(`${slug}-notes.md`, notesMarkdown(lesson))}><Download size={15} /> Download .md</button>
      </div>
      <article className="study-notes">
        <h1>{lesson.title}</h1>
        <p className="notes-intro">{lesson.introduction}</p>
        {lesson.sections.map((s, i) => (
          <section key={i}>
            <h2>{i + 1}. {s.heading}</h2>
            <ul>{(s.slide?.bullet_points || []).map((b, j) => <li key={j}>{b}</li>)}</ul>
            <p>{s.narration}</p>
          </section>
        ))}
        {lesson.sources?.length > 0 && <section><h2>Sources</h2><ul>{lesson.sources.map((s, i) => <li key={i}>{s.title} — {s.url}</li>)}</ul></section>}
      </article>
    </div>
  );
}
