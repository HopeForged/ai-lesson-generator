import { loadSetting, saveSetting } from './lecturers';

// Learner progress is kept in this browser (per lesson id): finished sections and quiz scores.
const empty = () => ({ visited: [], sections: {}, final: null });
export const getProgress = (lessonId) => (lessonId ? { ...empty(), ...loadSetting(`progress_${lessonId}`, {}) } : empty());
export function updateProgress(lessonId, mutate) {
  if (!lessonId) return empty();
  const next = mutate(getProgress(lessonId));
  saveSetting(`progress_${lessonId}`, next);
  return next;
}
export const markVisited = (lessonId, index) => updateProgress(lessonId, (p) => ({ ...p, visited: [...new Set([...p.visited, index])] }));
export const recordSectionScore = (lessonId, index, score, total) => updateProgress(lessonId, (p) => ({
  ...p, sections: { ...p.sections, [index]: { best: Math.max(score, p.sections[index]?.best ?? 0), total } } }));
export const recordFinalScore = (lessonId, score, total) => updateProgress(lessonId, (p) => ({ ...p, final: { best: Math.max(score, p.final?.best ?? 0), total } }));
