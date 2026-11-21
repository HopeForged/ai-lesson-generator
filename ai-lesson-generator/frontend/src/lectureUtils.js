// Helpers that turn a generated section into "beats": a spoken passage + the diagram shown with it.

export function splitSentences(text) {
  return (String(text || '').match(/[^.!?]+[.!?]+["')\]]*|[^.!?]+$/g) || []).map((s) => s.trim()).filter(Boolean);
}

function inferSceneType(text) {
  const value = text.toLowerCase();
  if (/\b(cycle|loop|repeat|again and again)\b/.test(value)) return 'cycle';
  if (/\b(first|next|then|step|process|stage|sequence)\b/.test(value)) return 'process';
  if (/\b(compare|whereas|difference|unlike|however)\b/.test(value)) return 'comparison';
  if (/\b(application|healthcare|education|transport|used in|for example)\b/.test(value)) return 'applications';
  if (/\b(network|connected|communicate|relationship)\b/.test(value)) return 'network';
  return 'concept';
}

/** Old lessons (or lessons where the AI gave no usable cues) get beats cut from the narration. */
function buildFallbackMoments(section) {
  const narration = section?.narration || '';
  let chunks = splitSentences(narration);
  if (chunks.length < 2) {
    const words = narration.split(/\s+/).filter(Boolean);
    const size = Math.max(1, Math.ceil(words.length / 3));
    chunks = [];
    for (let i = 0; i < words.length; i += size) chunks.push(words.slice(i, i + size).join(' '));
  }
  // group sentences into at most 4 beats so each beat has a few sentences, like a lecturer's paragraph
  const groups = Math.min(4, Math.max(1, Math.ceil(chunks.length / 2)));
  const perGroup = Math.ceil(chunks.length / groups);
  const beats = [];
  for (let i = 0; i < chunks.length; i += perGroup) beats.push(chunks.slice(i, i + perGroup).join(' '));
  const bullets = section?.slide?.bullet_points?.length ? section.slide.bullet_points : [section?.heading || 'Key idea'];
  return beats.map((cue_text, index) => {
    const items = [0, 1, 2].map((k) => bullets[(index + k) % bullets.length]).filter((v, i, a) => a.indexOf(v) === i).slice(0, 3);
    return {
      cue_text: splitSentences(cue_text)[0] || cue_text,
      avatar_action: index === 0 ? 'welcome' : 'explain',
      scene: {
        scene_type: inferSceneType(cue_text),
        title: bullets[index % bullets.length],
        description: section?.heading || '',
        items: items.length >= 2 ? items : [...items, section?.heading || 'Key idea'],
      },
    };
  });
}

/**
 * Returns [{ text, start, end, scene, avatar_action }]. beat.start/end are character offsets in the
 * section narration, so highlighting and speech stay aligned. Beat 0 always starts at 0 and the
 * last beat ends at the end of the narration, so everything the lecturer says belongs to a beat.
 */
export function buildBeats(section) {
  const narration = section?.narration || '';
  if (!narration) return [];
  const lower = narration.toLowerCase();
  const source = Array.isArray(section?.visual_moments) ? section.visual_moments : [];
  let from = 0;
  let mapped = source.map((moment) => {
    const cue = String(moment?.cue_text || '').trim();
    if (!cue) return null;
    let start = lower.indexOf(cue.toLowerCase(), from);
    if (start < 0) start = lower.indexOf(cue.split(/\s+/).slice(0, 5).join(' ').toLowerCase(), from);
    if (start < 0) return null;
    from = start + 1;
    return { ...moment, start };
  }).filter(Boolean);

  if (mapped.length < 2) {
    let at = 0;
    mapped = buildFallbackMoments(section).map((moment) => {
      const found = lower.indexOf(moment.cue_text.toLowerCase(), at);
      const start = found >= 0 ? found : at;
      at = start + 1;
      return { ...moment, start };
    });
  }
  // drop duplicate starts, then stretch the first beat back to 0
  mapped = mapped.filter((m, i) => i === 0 || m.start > mapped[i - 1].start);
  mapped[0].start = 0;
  return mapped.map((moment, i) => {
    const end = i + 1 < mapped.length ? mapped[i + 1].start : narration.length;
    return {
      ...moment,
      start: moment.start,
      end,
      text: narration.slice(moment.start, end).trim(),
      scene: moment.scene || section.visual_scene || {},
    };
  });
}

const STOP = new Set(['the', 'and', 'of', 'to', 'in', 'a', 'an', 'for', 'with', 'from', 'into', 'its', 'their']);

/**
 * For each diagram label, find where the lecturer first mentions it in the beat's text.
 * Labels that are never mentioned are revealed right after the previous label.
 */
export function mentionPositions(items, text, forceFirst = false) {
  const lower = String(text || '').toLowerCase();
  const found = items.map((item) => {
    const label = String(item).toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, ' ').replace(/\s+/g, ' ').trim();
    if (!label) return -1;
    let at = lower.indexOf(label);
    if (at >= 0) return at;
    const words = label.split(' ').filter((w) => w.length >= 4 && !STOP.has(w)).sort((a, b) => b.length - a.length);
    for (const word of words) {
      at = lower.indexOf(word.slice(0, Math.max(4, word.length - 2)));
      if (at >= 0) return at;
    }
    return -1;
  });
  const hits = found.filter((v) => v >= 0).length;
  if (hits < Math.ceil(items.length / 2)) {
    // labels are not named in the speech: spread them evenly across the beat
    return items.map((_, i) => Math.floor((text.length * i) / items.length * 0.9));
  }
  const out = [];
  found.forEach((value, i) => {
    out.push(value >= 0 ? value : (i === 0 ? 0 : out[i - 1] + 1));
  });
  if (forceFirst) out[0] = 0;
  return out;
}

/** Index (in the beat text) of the word being spoken at time t, from server word timings [{c,s,e}]. */
export function charAtTime(words, t) {
  let at = 0;
  for (const w of words || []) { if (w.s <= t) at = w.c; else break; }
  return at;
}

/** How open the mouth should be (0..1) at time t: it moves while a word is spoken and rests between words. */
export function mouthAtTime(words, t) {
  for (const w of words || []) {
    if (t >= w.s && t <= w.e + 0.04) {
      const cycle = Math.abs(Math.sin(((t - w.s) / 0.17) * Math.PI));
      return 0.3 + 0.7 * cycle;
    }
    if (w.s > t) break;
  }
  return 0;
}

export function hashText(text) {
  let h = 5381;
  for (let i = 0; i < text.length; i += 1) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}
