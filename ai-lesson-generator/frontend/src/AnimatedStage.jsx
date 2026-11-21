import { useEffect, useMemo, useRef, useState } from 'react';

/* Plays an AI-directed animation: actors on a 0..100 stage, steps fired by what the lecturer says. */

const TAGS = new Set(['svg', 'g', 'path', 'circle', 'ellipse', 'rect', 'line', 'polygon', 'polyline', 'text', 'tspan', 'defs', 'lineargradient', 'radialgradient', 'stop', 'animate', 'animatetransform', 'animatemotion']);
const ATTRS = new Set(['viewbox', 'width', 'height', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'd', 'points', 'fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'opacity', 'fill-opacity', 'stroke-opacity', 'transform', 'id', 'offset', 'stop-color', 'stop-opacity', 'text-anchor', 'font-size', 'font-weight', 'font-family', 'dominant-baseline', 'gradientunits', 'attributename', 'attributetype', 'from', 'to', 'values', 'dur', 'begin', 'repeatcount', 'keytimes', 'type', 'additive', 'calcmode', 'path', 'rotate', 'preserveaspectratio']);

export function safeSvg(markup) {
  try {
    if (typeof markup !== 'string' || markup.length > 4000 || /javascript:|<!|<\?|url\s*\(/i.test(markup)) return '';
    const doc = new DOMParser().parseFromString(markup, 'image/svg+xml');
    const root = doc.documentElement;
    if (!root || root.nodeName.toLowerCase() !== 'svg' || doc.querySelector('parsererror')) return '';
    const walk = (node) => {
      [...node.children].forEach((child) => {
        if (!TAGS.has(child.localName.toLowerCase())) { child.remove(); return; }
        walk(child);
      });
      [...node.attributes].forEach((a) => { if (!ATTRS.has(a.name.toLowerCase()) || /javascript:|url\s*\(/i.test(a.value)) node.removeAttribute(a.name); });
    };
    walk(root);
    root.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    return new XMLSerializer().serializeToString(root);
  } catch { return ''; }
}

/** Where in the beat text does each step fire? Phrases are searched forward; misses are spread evenly. */
export function stepTriggers(steps, text) {
  const low = String(text || '').toLowerCase();
  const total = Math.max(low.length, 1);
  let cursor = 0;
  const found = steps.map((s) => {
    const phrase = String(s.say || '').toLowerCase().trim();
    if (!phrase) return -1;
    let at = low.indexOf(phrase, cursor);
    if (at < 0) at = low.indexOf(phrase);
    if (at < 0) return -1;
    cursor = Math.max(cursor, at);
    return at;
  });
  // steps without a match: interpolate between the neighbours that matched
  return found.map((p, i) => {
    if (p >= 0) return p;
    let prev = -1, next = -1;
    for (let k = i - 1; k >= 0; k -= 1) if (found[k] >= 0) { prev = k; break; }
    for (let k = i + 1; k < found.length; k += 1) if (found[k] >= 0) { next = k; break; }
    const a = prev >= 0 ? found[prev] : 0;
    const b = next >= 0 ? found[next] : total * 0.9;
    const from = prev >= 0 ? prev : -1, to = next >= 0 ? next : found.length;
    return a + ((b - a) * (i - from)) / (to - from);
  });
}

/** Replay fired steps to get the state of every actor. */
export function replay(anim, fired) {
  const st = {};
  anim.actors.forEach((a) => {
    st[a.id] = { shown: false, x: a.x, y: a.y, label: a.label, icon: a.icon, detail: a.detail, scale: 1, fill: 0, count: 0, badge: '', orbit: null, shake: 0, pulse: 0, drawn: [], shiftX: 0, shiftY: 0, gone: false };
  });
  const tokens = [];
  fired.forEach((step, k) => {
    const s = st[step.actor];
    if (!s) return;
    const to = step.to && st[step.to] ? st[step.to] : null;
    if (step.do !== 'disappear') { s.shown = true; s.gone = false; }
    if (to && (step.do === 'send' || step.do === 'stream')) to.shown = true;
    switch (step.do) {
      case 'disappear': s.gone = true; break;
      case 'move': if (step.x != null) s.x = step.x; if (step.y != null) s.y = step.y; break;
      case 'send': case 'stream':
        if (to) tokens.push({ key: k, from: { x: s.x, y: s.y }, to: { x: to.x, y: to.y }, text: step.text, icon: step.icon, many: step.do === 'stream' });
        break;
      case 'pulse': s.pulse = k + 1; break;
      case 'grow': s.scale = step.value || 1.3; break;
      case 'shrink': s.scale = step.value || 0.7; break;
      case 'transform': if (step.text) s.label = step.text; if (step.icon) s.icon = step.icon; break;
      case 'fill': s.fill = Math.max(0, Math.min(100, step.value ?? 100)); break;
      case 'count': s.count = step.value ?? 0; break;
      case 'check': s.badge = 'check'; break;
      case 'cross': s.badge = 'cross'; break;
      case 'orbit': if (to) s.orbit = { cx: to.x, cy: to.y }; break;
      case 'shake': s.shake = k + 1; break;
      case 'draw': { const i = Math.round(step.series ?? 0); if (!s.drawn.includes(i)) s.drawn = [...s.drawn, i]; break; }
      case 'shift': s.shiftX += step.x || 0; s.shiftY += step.y || 0; s.drawn = s.drawn.length ? s.drawn : [0]; break;
      default: break;
    }
  });
  return { st, tokens };
}

function useTween(target, ms = 900) {
  const [v, setV] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    const start = performance.now(); const a = from.current;
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / ms); const e = 1 - (1 - p) ** 3;
      from.current = a + (target - a) * e; setV(from.current);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}

function Counter({ actor, s }) {
  const v = useTween(s.count);
  const text = Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : (Math.round(v * 10) / 10).toString();
  return <div className="as-counter"><strong>{actor.prefix}{text}{actor.suffix}</strong></div>;
}

function Chart({ actor, s }) {
  const all = actor.series.flat();
  const lo = Math.min(...all), hi = Math.max(...all); const span = hi - lo || 1;
  const COLORS = ['var(--accent)', '#ffb35c', '#5cd6a6'];
  const px = (i, n) => 8 + (i * 84) / Math.max(n - 1, 1);
  const py = (v) => 50 - ((v - lo) / span) * 40;
  return (
    <svg className="as-plot" viewBox="0 0 100 60">
      <line x1="8" y1="52" x2="94" y2="52" className="as-axis" /><line x1="8" y1="6" x2="8" y2="52" className="as-axis" />
      {actor.series.map((line, si) => {
        const on = s.drawn.includes(si); const moved = si === s.drawn[s.drawn.length - 1] || s.drawn.length === 1;
        const tf = moved ? `translate(${s.shiftX * 0.5} ${-s.shiftY * 0.5})` : undefined;
        if (actor.chart_type === 'bar') {
          const bw = 70 / line.length / (actor.series.length + 0.4);
          return (
            <g key={si} style={{ transform: tf, transition: 'transform .9s ease' }}>
              {line.map((v, i) => (
                <rect key={i} x={px(i, line.length) - 3 + si * bw} width={bw} rx=".8" y={on ? py(v) : 52} height={on ? 52 - py(v) : 0} fill={COLORS[si]} className="as-bar" style={{ transitionDelay: `${i * 60}ms` }} />
              ))}
            </g>
          );
        }
        return (
          <g key={si} style={{ transform: tf, transition: 'transform .9s ease' }}>
            <polyline pathLength="1" className="as-line" style={{ strokeDashoffset: on ? 0 : 1 }} stroke={COLORS[si]} fill="none" points={line.map((v, i) => `${px(i, line.length)},${py(v)}`).join(' ')} />
            {on && <circle r="1.6" fill={COLORS[si]} cx={px(line.length - 1, line.length)} cy={py(line[line.length - 1])} />}
          </g>
        );
      })}
      {actor.series_names?.map((n, i) => <text key={i} x={12 + i * 30} y="58" className="as-legend" fill={COLORS[i]}>● {n}</text>)}
    </svg>
  );
}

export default function AnimatedStage({ animation, beatText, beatPos, playing, resolveIcon }) {
  const triggers = useMemo(() => stepTriggers(animation.steps, beatText), [animation, beatText]);
  const fired = useMemo(() => animation.steps
    .map((s, i) => ({ s, t: triggers[i], i }))
    .filter((x) => !playing || beatPos >= x.t)
    .sort((a, b) => a.t - b.t || a.i - b.i)
    .map((x) => x.s), [animation, triggers, beatPos, playing]);
  const { st, tokens } = useMemo(() => replay(animation, fired), [animation, fired]);
  const svgs = useMemo(() => Object.fromEntries(animation.actors.filter((a) => a.kind === 'svg').map((a) => [a.id, safeSvg(a.svg)])), [animation]);
  const lastStep = fired[fired.length - 1];

  return (
    <div className="as-stage">
      {tokens.filter(() => playing).map((t) => {
        const Icon = resolveIcon?.(t.icon, t.text || '', '', 0);
        return [...Array(t.many ? 3 : 1)].map((_, n) => (
          <div key={`${t.key}-${n}`} className="as-token" style={{ '--x1': `${t.from.x}%`, '--y1': `${t.from.y}%`, '--x2': `${t.to.x}%`, '--y2': `${t.to.y}%`, animationDelay: `${n * 0.35}s` }}>
            {Icon && <Icon strokeWidth={2} />}{t.text && <span>{t.text}</span>}
          </div>
        ));
      })}
      {animation.actors.map((a) => {
        const s = st[a.id];
        if (!s.shown || s.gone) return null;
        const Icon = resolveIcon?.(s.icon, s.label, s.detail, 0);
        const cls = ['as-actor', `as-${a.kind}`, lastStep && lastStep.actor === a.id && playing ? 'is-focus' : '', s.orbit ? 'is-orbit' : ''].join(' ');
        const style = { left: `${s.x}%`, top: `${s.y}%`, '--sc': s.scale, '--ox': s.orbit ? `${s.orbit.cx - s.x}%` : '0%', '--oy': s.orbit ? `${s.orbit.cy - s.y}%` : '0%' };
        return (
          <div key={a.id} className={cls} style={style}>
            <div key={`shake${s.shake}`} className={s.shake ? 'as-shake' : ''}>
              <div key={`pulse${s.pulse}`} className={s.pulse ? 'as-pulse' : ''}>
                {a.kind === 'node' && <div className="as-icon">{Icon ? <Icon strokeWidth={1.7} /> : <span>{s.label.slice(0, 1)}</span>}</div>}
                {a.kind === 'counter' && <Counter actor={a} s={s} />}
                {a.kind === 'meter' && <div className="as-meter"><i style={{ width: `${s.fill}%` }} /></div>}
                {a.kind === 'chart' && <Chart actor={a} s={s} />}
                {a.kind === 'svg' && <div className="as-svg" dangerouslySetInnerHTML={{ __html: svgs[a.id] }} />}
                <b>{s.label}</b>
                {s.detail && a.kind === 'node' && <small>{s.detail}</small>}
                {s.badge && <em className={`as-badge ${s.badge}`}>{s.badge === 'check' ? '✓' : '✕'}</em>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
