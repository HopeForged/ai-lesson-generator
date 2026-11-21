import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import { charAtTime, hashText, mouthAtTime } from './lectureUtils';
import { LANG_TAG } from './lecturers';

/**
 * Plays a list of beats one after another. Prefers the free neural voice from the backend
 * (exact word timings -> perfect highlighting and lip-sync) and falls back to the browser's voice.
 */
export function usePlayer({ beats, language, lecturer, rate, voiceName, voices, onFinish }) {
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [beatIndex, setBeatIndex] = useState(0);
  const [beatPos, setBeatPos] = useState(0);
  const [mouth, setMouth] = useState(null);       // null = use the CSS talking animation
  const [preparing, setPreparing] = useState(false);
  const [voiceMode, setVoiceMode] = useState('unknown'); // unknown | server | browser

  const live = useRef({});
  live.current = { beats, language, lecturer, rate, voiceName, voices, onFinish };
  const token = useRef(0);
  const timers = useRef({ tick: null, gap: null, raf: null });
  const audioRef = useRef(null);
  const pendingNext = useRef(null);
  const pausedRef = useRef(false);
  const currentBeat = useRef(0);
  const finished = useRef(false);
  const serverOk = useRef(null);
  const clipCache = useRef(new Map());

  function clearTimers() {
    const t = timers.current;
    if (t.tick) window.clearInterval(t.tick);
    if (t.gap) window.clearTimeout(t.gap);
    if (t.raf) window.cancelAnimationFrame(t.raf);
    timers.current = { tick: null, gap: null, raf: null };
  }

  function stop() {
    token.current += 1;
    clearTimers();
    pendingNext.current = null;
    pausedRef.current = false;
    if (audioRef.current) { audioRef.current.pause(); audioRef.current.src = ''; audioRef.current = null; }
    window.speechSynthesis?.cancel?.();
    setSpeaking(false); setPaused(false); setMouth(null); setPreparing(false);
  }

  useEffect(() => () => { stop(); }, []); // eslint-disable-line

  /** Fetch (or reuse) the voice clips for a list of beats. Resolves null if the server voice is unavailable. */
  async function getClips(list) {
    if (serverOk.current === false || !list.length) return null;
    const { language: lang, lecturer: who, rate: speed } = live.current;
    const key = `${lang}|${who}|${speed}|${hashText(list.map((b) => b.text).join('\n'))}`;
    if (clipCache.current.has(key)) return clipCache.current.get(key);
    try {
      const res = await api.tts({ texts: list.map((b) => b.text), language: lang, lecturer: who, rate: Number(speed) });
      const clips = res.clips;
      if (!clips || clips.length !== list.length || clips.some((c) => c.provider === 'silent')) throw new Error('no voice');
      clipCache.current.set(key, clips);
      serverOk.current = true;
      return clips;
    } catch {
      serverOk.current = false;
      return null;
    }
  }

  function prefetch(list) { if (serverOk.current !== false) getClips(list); }

  function next(i, tk, runner) {
    const list = live.current.beats;
    if (i + 1 < list.length) {
      timers.current.gap = window.setTimeout(() => {
        timers.current.gap = null;
        if (tk !== token.current) return;
        if (pausedRef.current) pendingNext.current = { i: i + 1, runner }; else runner(i + 1, tk);
      }, 450);
    } else {
      clearTimers();
      finished.current = true;
      setSpeaking(false); setPaused(false); setMouth(null);
      live.current.onFinish?.(tk);
    }
  }

  function runServerBeat(i, tk, clips) {
    const beat = live.current.beats[i];
    const clip = clips[i];
    if (!beat || !clip || tk !== token.current) return;
    currentBeat.current = i;
    setBeatIndex(i); setBeatPos(0);
    const audio = new Audio(clip.url);
    audioRef.current = audio;
    const loop = () => {
      if (tk !== token.current) return;
      if (!audio.paused) {
        setBeatPos(charAtTime(clip.words, audio.currentTime));
        setMouth(mouthAtTime(clip.words, audio.currentTime));
      }
      timers.current.raf = window.requestAnimationFrame(loop);
    };
    audio.onended = () => {
      if (tk !== token.current) return;
      if (timers.current.raf) window.cancelAnimationFrame(timers.current.raf);
      setMouth(0);
      next(i, tk, (n, t) => runServerBeat(n, t, clips));
    };
    audio.onerror = () => { if (tk === token.current) { serverOk.current = false; playBrowser(i, tk); } };
    audio.play().then(() => { if (tk === token.current) loop(); }).catch(() => { if (tk === token.current) { serverOk.current = false; playBrowser(i, tk); } });
  }

  function runBrowserBeat(i, tk) {
    const { beats: list, voices: voiceList, voiceName: chosen, rate: speed, language: lang } = live.current;
    if (tk !== token.current) return;
    const beat = list[i];
    if (!beat) return;
    setMouth(null);
    const utterance = new SpeechSynthesisUtterance(beat.text);
    const voice = voiceList.find((v) => v.name === chosen);
    if (voice) { utterance.voice = voice; utterance.lang = voice.lang; } else utterance.lang = LANG_TAG[lang] || 'en-US';
    utterance.rate = Number(speed);
    let boundarySeen = false;
    currentBeat.current = i;
    setBeatIndex(i); setBeatPos(0);
    utterance.onstart = () => {
      if (tk !== token.current) return;
      setSpeaking(true);
      const words = beat.text.split(/\s+/).length;
      const duration = Math.max(2500, (words / (2.45 * Number(speed))) * 1000);
      let elapsed = 0; let last = Date.now();
      if (timers.current.tick) window.clearInterval(timers.current.tick);
      timers.current.tick = window.setInterval(() => {
        const now = Date.now();
        if (!window.speechSynthesis?.paused) elapsed += now - last;
        last = now;
        if (!boundarySeen) setBeatPos(Math.floor(beat.text.length * Math.min(0.98, elapsed / duration)));
      }, 200);
    };
    utterance.onboundary = (event) => { if (tk === token.current && typeof event.charIndex === 'number') { boundarySeen = true; setBeatPos(event.charIndex); } };
    utterance.onend = () => {
      if (tk !== token.current) return;
      if (timers.current.tick) window.clearInterval(timers.current.tick);
      timers.current.tick = null;
      next(i, tk, runBrowserBeat);
    };
    utterance.onerror = (event) => { if (tk === token.current && event?.error !== 'interrupted' && event?.error !== 'canceled') stop(); };
    window.speechSynthesis.speak(utterance);
  }

  function playBrowser(i, tk) {
    if (!('speechSynthesis' in window)) { stop(); return; }
    setVoiceMode('browser');
    runBrowserBeat(i, tk);
  }

  async function playFrom(i) {
    if (!live.current.beats.length) return;
    stop();
    finished.current = false;
    const tk = token.current;
    setSpeaking(true); setBeatIndex(i); setBeatPos(0);
    setPreparing(serverOk.current !== false);
    const clips = await getClips(live.current.beats);
    if (tk !== token.current) return;
    setPreparing(false);
    if (clips) { setVoiceMode('server'); runServerBeat(i, tk, clips); } else window.setTimeout(() => playBrowser(i, tk), 80);
  }

  function togglePlay() {
    if (!speaking) { playFrom(finished.current ? 0 : currentBeat.current); return; }
    if (!paused) {
      audioRef.current?.pause();
      window.speechSynthesis?.pause?.();
      pausedRef.current = true; setPaused(true); setMouth((m) => (m === null ? null : 0));
      return;
    }
    pausedRef.current = false; setPaused(false);
    if (audioRef.current) audioRef.current.play().catch(() => {});
    else window.speechSynthesis?.resume?.();
    if (pendingNext.current) {
      const { i, runner } = pendingNext.current;
      pendingNext.current = null;
      runner(i, token.current);
    } else if (!audioRef.current) {
      const tk = token.current;
      window.setTimeout(() => {
        if (tk === token.current && !pausedRef.current && !window.speechSynthesis.speaking && !timers.current.gap) runBrowserBeat(currentBeat.current, tk);
      }, 350);
    }
  }

  function pickBeat(i) {
    if (speaking) { playFrom(i); return; }
    finished.current = false;
    currentBeat.current = i;
    setBeatIndex(i); setBeatPos(0);
  }

  /** Called when the section or lesson changes: stop and go back to the first beat. */
  function reset() {
    stop();
    setBeatIndex(0); setBeatPos(0);
    currentBeat.current = 0;
    finished.current = false;
  }

  return { speaking, paused, beatIndex, beatPos, mouth, preparing, voiceMode, playFrom, togglePlay, pickBeat, stop, reset, prefetch };
}
