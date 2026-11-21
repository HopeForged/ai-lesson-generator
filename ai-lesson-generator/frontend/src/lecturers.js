export const LECTURERS = [
  { id: 'mensah', name: 'Dr. Mensah', blurb: 'Calm and clear' },
  { id: 'naledi', name: 'Prof. Naledi', blurb: 'Warm and encouraging' },
  { id: 'walker', name: 'Mr. Walker', blurb: 'Relaxed and practical' },
];
export const LANGUAGES = ['English', 'English (UK)', 'English (South Africa)', 'French', 'Spanish', 'Portuguese', 'German', 'Italian', 'Swahili', 'Zulu', 'Afrikaans', 'Arabic', 'Hindi', 'Chinese'];
export const LEVELS = [
  { id: 'beginner', label: 'Beginner' },
  { id: 'intermediate', label: 'Intermediate' },
  { id: 'advanced', label: 'Advanced' },
  { id: 'exam', label: 'Exam prep' },
];
// BCP-47 tag for the browser's built-in voice / speech recognition, per lesson language
export const LANG_TAG = { English: 'en-US', 'English (UK)': 'en-GB', 'English (South Africa)': 'en-ZA', French: 'fr-FR', Spanish: 'es-ES', Portuguese: 'pt-BR', German: 'de-DE', Italian: 'it-IT', Swahili: 'sw-KE', Zulu: 'zu-ZA', Afrikaans: 'af-ZA', Arabic: 'ar-SA', Hindi: 'hi-IN', Chinese: 'zh-CN' };

export function loadSetting(key, fallback) {
  try { const v = window.localStorage.getItem(`lf_${key}`); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
}
export function saveSetting(key, value) {
  try { window.localStorage.setItem(`lf_${key}`, JSON.stringify(value)); } catch { /* private mode */ }
}
