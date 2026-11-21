import { useId, useMemo } from 'react';
import AnimatedStage from './AnimatedStage';
import * as Lucide from 'lucide-react';
import { mentionPositions } from './lectureUtils';
import './board.css';

/* ---------- icons ---------- */
const ICONS = {
  sun: ['Sun'], leaf: ['Leaf'], droplets: ['Droplets', 'Droplet'], wind: ['Wind'], flame: ['Flame'], snowflake: ['Snowflake'],
  zap: ['Zap'], atom: ['Atom'], flask: ['FlaskConical', 'Flask'], dna: ['Dna'], heart: ['HeartPulse', 'Heart'], brain: ['Brain'],
  eye: ['Eye'], ear: ['Ear'], bone: ['Bone'], cpu: ['Cpu'], database: ['Database'], network: ['Network'], server: ['Server'],
  cloud: ['Cloud'], shield: ['ShieldCheck', 'Shield'], lock: ['Lock'], key: ['Key'], globe: ['Globe'], map: ['Map', 'MapPin'],
  building: ['Building2', 'Building'], factory: ['Factory'], home: ['House', 'Home'], car: ['Car'], plane: ['Plane'], ship: ['Ship'],
  train: ['TrainFront', 'Train'], rocket: ['Rocket'], book: ['BookOpen', 'Book'], pencil: ['Pencil'], calculator: ['Calculator'],
  chart: ['ChartColumn', 'BarChart3', 'BarChart'], clock: ['Clock'], calendar: ['Calendar'], coins: ['Coins'], wallet: ['Wallet'],
  cart: ['ShoppingCart'], truck: ['Truck'], users: ['Users'], user: ['User'], message: ['MessageCircle', 'MessageSquare'], mail: ['Mail'],
  phone: ['Phone'], camera: ['Camera'], music: ['Music'], video: ['Video'], lightbulb: ['Lightbulb'], target: ['Target'], flag: ['Flag'],
  star: ['Star'], check: ['CircleCheck', 'CheckCircle2', 'Check'], search: ['Search'], settings: ['Settings'], wrench: ['Wrench'],
  hammer: ['Hammer'], tree: ['TreePine', 'Trees'], flower: ['Flower2', 'Flower'], mountain: ['Mountain'], wave: ['Waves'],
  thermometer: ['Thermometer'], microscope: ['Microscope'], pill: ['Pill'], stethoscope: ['Stethoscope'], scale: ['Scale'],
  gavel: ['Gavel'], graduation: ['GraduationCap'], trophy: ['Trophy'], puzzle: ['Puzzle'], gear: ['Cog'], code: ['Code2', 'Code'],
  wifi: ['Wifi'], battery: ['Battery'], magnet: ['Magnet'],
};
const KEYWORDS = [
  [/sun|solar|sunlight/, 'sun'], [/leaf|chloroplast|chlorophyll|photosynth/, 'leaf'], [/water|rain|h2o|liquid|river/, 'droplets'],
  [/oxygen|carbon dioxide|co2|air|gas|wind|breath/, 'wind'], [/fire|heat|combust|burn/, 'flame'], [/electric|power|voltage|current|energy/, 'zap'],
  [/atom|molecul|electron|proton|particle/, 'atom'], [/experiment|chemical|reaction|lab/, 'flask'], [/dna|gene|cell/, 'dna'],
  [/heart|blood|pulse|health/, 'heart'], [/brain|neural|mind|think|learn/, 'brain'], [/computer|processor|cpu|chip|hardware/, 'cpu'],
  [/data|storage|record|memory/, 'database'], [/network|internet|connect|link/, 'network'], [/server|host/, 'server'],
  [/cloud|weather/, 'cloud'], [/secur|protect|privacy|safe|encrypt/, 'shield'], [/world|global|earth|country|planet/, 'globe'],
  [/factory|industr|manufactur|produc/, 'factory'], [/money|cost|price|econom|financ|profit|coin/, 'coins'], [/people|team|community|society|users|students/, 'users'],
  [/book|read|text|theory|lesson/, 'book'], [/time|history|year|era|period/, 'clock'], [/goal|aim|target|objective/, 'target'],
  [/idea|insight|principle|concept/, 'lightbulb'], [/result|output|outcome|complete|success|product/, 'check'], [/tool|build|repair|engineer/, 'wrench'],
  [/code|program|software|algorithm/, 'code'], [/law|legal|rule|court|govern/, 'gavel'], [/chart|statistic|growth|trend|measure/, 'chart'],
  [/plant|tree|forest|grow/, 'tree'], [/medic|drug|treat|doctor/, 'stethoscope'], [/search|find|discover|research/, 'search'],
];
export function resolveIcon(name, label, detail, index) {
  const lookup = (key) => (ICONS[key] || []).map((n) => Lucide[n]).find(Boolean);
  const direct = name && lookup(String(name).toLowerCase().replace(/[^a-z]/g, ''));
  if (direct) return direct;
  const text = `${label} ${detail || ''}`.toLowerCase();
  const rule = KEYWORDS.find(([re]) => re.test(text));
  return (rule && lookup(rule[1])) || null;
}

/* ---------- layouts (board is 160 x 90 units) ---------- */
const W = 160, H = 90, CX = 80, CY = 45;
const rad = (deg) => (deg * Math.PI) / 180;
const rowXs = (n, span = 128) => {
  if (n === 1) return [CX];
  const step = Math.min(34, span / (n - 1));
  return Array.from({ length: n }, (_, i) => CX + (i - (n - 1) / 2) * step);
};

const LAYOUT_FOR = { process: 'flow', timeline: 'timeline', cycle: 'cycle', comparison: 'comparison', applications: 'grid', network: 'network', structure: 'hub', concept: 'hub', generic: 'flow' };

function computeLayout(type, n) {
  let layout = LAYOUT_FOR[type] || 'flow';
  if (layout === 'comparison' && n > 3) layout = 'grid';
  if ((layout === 'hub' || layout === 'network') && n < 3) layout = 'flow';
  if (layout === 'cycle' && n < 3) layout = 'flow';
  const nodes = []; const edges = []; let axis = null;

  if (layout === 'flow') {
    if (n <= 5) rowXs(n).forEach((x, i) => nodes.push({ x, y: CY }));
    else {
      const xs = rowXs(3, 100);
      for (let i = 0; i < n; i += 1) {
        const row = i < 3 ? 0 : 1; const col = row === 0 ? i : 5 - i; // serpentine: second row runs back
        nodes.push({ x: xs[Math.min(2, Math.max(0, col))], y: row === 0 ? 26 : 65 });
      }
    }
    for (let i = 0; i < n - 1; i += 1) edges.push([i, i + 1]);
  } else if (layout === 'timeline') {
    rowXs(n).forEach((x, i) => nodes.push({ x, y: i % 2 === 0 ? 24 : 66, axisX: x }));
    axis = { y: CY, x1: 10, x2: 150 };
  } else if (layout === 'cycle') {
    for (let i = 0; i < n; i += 1) {
      const a = rad(-90 + (i * 360) / n);
      nodes.push({ x: CX + 50 * Math.cos(a), y: CY + 26 * Math.sin(a) });
    }
    for (let i = 0; i < n; i += 1) edges.push([i, (i + 1) % n]);
  } else if (layout === 'hub' || layout === 'network') {
    nodes.push({ x: CX, y: CY, hub: true });
    const m = n - 1;
    for (let i = 0; i < m; i += 1) {
      const a = rad(-90 + ((i + 0.5) * 360) / m);
      nodes.push({ x: CX + 55 * Math.cos(a), y: CY + 29 * Math.sin(a) });
    }
    for (let i = 1; i < n; i += 1) edges.push([0, i]);
    if (layout === 'network' && m > 2) for (let i = 1; i < n; i += 1) edges.push([i, i === n - 1 ? 1 : i + 1, 'soft']);
  } else if (layout === 'comparison') {
    (n === 2 ? [42, 118] : [27, 80, 133]).forEach((x) => nodes.push({ x, y: CY, card: true }));
  } else { // grid
    const rows = n <= 3 ? [n] : n === 4 ? [2, 2] : n === 5 ? [3, 2] : [3, 3];
    const ys = rows.length === 1 ? [CY] : [27, 65];
    rows.forEach((count, r) => (count === 3 ? [28, 80, 132] : count === 2 ? (rows.length === 1 ? [42, 118] : [54, 106]) : [CX]).forEach((x) => nodes.push({ x, y: ys[r], card: true })));
  }
  return { layout, nodes, edges, axis };
}

/** Shorten a line so arrows stop at the edge of the node boxes. */
function trim(a, b, ra, rb) {
  const dx = b.x - a.x, dy = b.y - a.y; const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len, uy = dy / len;
  // nodes are roughly 26 x 28 units, so use the distance to the box edge along the line direction
  const edgeDist = (r) => Math.min(r.w / 2 / Math.max(Math.abs(ux), 0.001), r.h / 2 / Math.max(Math.abs(uy), 0.001));
  const s = edgeDist(ra) + 1.2, e = edgeDist(rb) + 1.6;
  if (s + e >= len) return null;
  return { x1: a.x + ux * s, y1: a.y + uy * s, x2: b.x - ux * e, y2: b.y - uy * e, len: len - s - e };
}

const TYPE_LABEL = { process: 'HOW IT WORKS', cycle: 'A CYCLE', comparison: 'COMPARE', timeline: 'TIMELINE', applications: 'IN THE REAL WORLD', network: 'HOW THE PARTS CONNECT', structure: 'PARTS OF THE WHOLE', concept: 'THE BIG IDEA', generic: 'ON THE BOARD' };

export default function VisualScene({
  scene, beatText = '', beatPos = 0, playing = false, paused = false,
  beatNumber = 1, beatCount = 1, sectionIndex = 0, onPickBeat, compact = false,
}) {
  const animated = !!(scene?.animation && Array.isArray(scene.animation.actors) && Array.isArray(scene.animation.steps));
  const uid = useId().replace(/[:]/g, '');
  const safe = scene || {};
  const type = TYPE_LABEL[safe.scene_type] ? safe.scene_type : 'generic';
  const items = useMemo(() => {
    const list = (Array.isArray(safe.items) ? safe.items : []).map(String).filter(Boolean).slice(0, 6);
    return list.length >= 2 ? list : [...list, 'Key idea', 'Result'].slice(0, Math.max(2, list.length));
  }, [safe.items]);
  const details = Array.isArray(safe.details) ? safe.details : [];
  const icons = Array.isArray(safe.icons) ? safe.icons : [];
  const { layout, nodes, edges, axis } = useMemo(() => computeLayout(type, items.length), [type, items.length]);

  // When does the lecturer mention each label? That decides what is revealed and highlighted.
  const mentions = useMemo(() => mentionPositions(items, beatText, layout === 'hub' || layout === 'network'), [items, beatText, layout]);
  const revealed = items.map((_, i) => !playing || beatPos >= mentions[i]);
  let focus = -1;
  if (playing) mentions.forEach((m, i) => { if (beatPos >= m && (focus < 0 || m >= mentions[focus])) focus = i; });
  const sizeOf = (i) => (layout === 'comparison' ? { w: items.length === 2 ? 44 : 38, h: 52 } : nodes[i]?.card ? { w: 38, h: 30 } : nodes[i]?.hub ? { w: 34, h: 32 } : { w: 27, h: 30 });
  const lines = edges.map(([a, b, kind], i) => {
    const t = trim(nodes[a], nodes[b], sizeOf(a), sizeOf(b));
    return t && { ...t, a, b, kind, i };
  }).filter(Boolean);

  return (
    <section className={`board layout-${layout} ${playing && !paused ? 'is-live' : ''} ${compact ? 'is-compact' : ''}`} style={{ '--hue': [262, 168, 32, 338, 204, 130][sectionIndex % 6] }} aria-label="Teaching board">
      <header className="board-head">
        <span className="board-tag">{TYPE_LABEL[type]} · DIAGRAM {beatNumber} OF {beatCount}</span>
        <h3>{safe.title || 'Explore the idea'}</h3>
        {safe.description && !compact && <p>{safe.description}</p>}
      </header>

      <div className="board-canvas">
        {animated && <AnimatedStage animation={safe.animation} beatText={beatText} beatPos={beatPos} playing={playing} resolveIcon={resolveIcon} />}
        {!animated && <svg className="board-lines" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
          <defs>
            <marker id={`arrow-${uid}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4.4" markerHeight="4.4" orient="auto"><path d="M1 1 L9 5 L1 9 Z" className="arrow-head" /></marker>
          </defs>
          {axis && (
            <g className="axis">
              <line x1={axis.x1} y1={axis.y} x2={axis.x2} y2={axis.y} markerEnd={`url(#arrow-${uid})`} />
              {nodes.map((n, i) => {
                const up = n.y < axis.y;
                return <g key={i} className={`axis-tick ${revealed[i] ? 'on' : ''}`}><line x1={n.x} y1={axis.y} x2={n.x} y2={n.y + (up ? 15 : -15)} /><circle cx={n.x} cy={axis.y} r="2.1" /></g>;
              })}
            </g>
          )}
          {lines.map((l) => {
            const lit = revealed[l.a] && revealed[l.b];
            return (
              <g key={l.i} className={`edge ${lit ? 'lit' : ''} ${l.kind || ''}`}>
                <line className="edge-ghost" x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} />
                <line className="edge-draw" pathLength="1" x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} markerEnd={l.kind === 'soft' ? undefined : `url(#arrow-${uid})`} />
                {lit && l.kind !== 'soft' && [0, 1].map((k) => (
                  <circle key={k} className="particle" r="1.15" cx={l.x1} cy={l.y1}
                    style={{ '--dx': `${l.x2 - l.x1}px`, '--dy': `${l.y2 - l.y1}px`, animationDelay: `${k * 1.1}s`, animationDuration: `${Math.max(1.6, l.len / 14)}s` }} />
                ))}
              </g>
            );
          })}
          {axis && revealed.every(Boolean) && <circle className="particle" r="1.3" cx={axis.x1} cy={axis.y} style={{ '--dx': `${axis.x2 - axis.x1 - 6}px`, '--dy': '0px', animationDuration: '5s' }} />}
          {layout === 'comparison' && items.length === 2 && <g className="vs"><circle cx={CX} cy={CY} r="6.5" /><text x={CX} y={CY + 2.3} textAnchor="middle">VS</text></g>}
        </svg>}

        {!animated && items.map((label, i) => {
          const Icon = resolveIcon(icons[i], label, details[i], i);
          const node = nodes[i];
          const cls = ['bnode', node.hub ? 'is-hub' : '', node.card ? 'is-card' : '', layout === 'comparison' ? 'is-compare' : '', revealed[i] ? 'is-shown' : 'is-ghost', focus === i ? 'is-focus' : '', playing && focus >= 0 && focus !== i && revealed[i] ? 'is-dim' : ''].filter(Boolean).join(' ');
          return (
            <div key={`${label}-${i}`} className={cls} style={{ left: `${(node.x / W) * 100}%`, top: `${(node.y / H) * 100}%`, '--i': i }}>
              <div className="bnode-icon">{Icon ? <Icon strokeWidth={1.7} /> : <span>{i + 1}</span>}</div>
              <b>{label}</b>
              {details[i] && <small>{details[i]}</small>}
              {focus === i && <i className="bnode-ping" />}
            </div>
          );
        })}
        {!animated && layout === 'cycle' && <div className="cycle-center"><span>{safe.title}</span></div>}
      </div>

      {!compact && <footer className="board-foot">
        <div className="beat-dots" role="tablist" aria-label="Diagrams in this section">
          {Array.from({ length: beatCount }, (_, i) => (
            <button key={i} type="button" role="tab" aria-selected={i + 1 === beatNumber} aria-label={`Diagram ${i + 1}`} className={i + 1 === beatNumber ? 'on' : i + 1 < beatNumber ? 'done' : ''} onClick={() => onPickBeat?.(i)} />
          ))}
        </div>
        <span className="board-live"><i /> {playing ? (paused ? 'Paused' : 'The lecturer is explaining this diagram') : 'Press play, or pick a diagram'}</span>
      </footer>}
    </section>
  );
}
