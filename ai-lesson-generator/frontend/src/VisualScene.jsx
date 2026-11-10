import { useMemo } from 'react';

const SCENE_LABELS = {
  concept: 'KEY CONCEPT', process: 'HOW IT WORKS', comparison: 'COMPARISON',
  timeline: 'TIMELINE', applications: 'REAL-WORLD USES', network: 'CONNECTED SYSTEM', generic: 'VISUAL EXPLANATION'
};

export default function VisualScene({ scene, active, momentNumber = 1, momentCount = 1, cueText = '' }) {
  const safeScene = scene || {};
  const type = SCENE_LABELS[safeScene.scene_type] ? safeScene.scene_type : 'generic';
  const items = useMemo(() => (Array.isArray(safeScene.items) ? safeScene.items : []).filter(Boolean).slice(0, 5), [safeScene.items]);
  const labels = items.length >= 2 ? items : ['Main idea', 'Supporting idea'];

  return (
    <section className={`visual-scene scene-${type} ${active ? 'scene-active' : ''}`} aria-label="AI planned animated visual">
      <div className="visual-scene-heading">
        <span className="visual-scene-tag">AI VISUAL PLAN · SCENE {momentNumber} OF {momentCount} · {SCENE_LABELS[type]}</span>
        <h3>{safeScene.title || 'Explore the idea'}</h3>
        <p>{safeScene.description || 'A visual explanation of this lesson section.'}</p>
        {cueText && <div className="visual-cue"><span>NOW EXPLAINING</span>{cueText}</div>}
      </div>

      {type === 'process' || type === 'timeline' ? (
        <div className={`scene-flow ${type === 'timeline' ? 'timeline-flow' : ''}`}>
          {labels.map((item, index) => <div className="scene-step" key={`${item}-${index}`} style={{ '--step': index }}>
            <span className="scene-step-number">{index + 1}</span><strong>{item}</strong>
            {index < labels.length - 1 && <span className="scene-connector" aria-hidden="true">→</span>}
          </div>)}
        </div>
      ) : type === 'comparison' ? (
        <div className="scene-comparison">
          {labels.map((item, index) => <div className="comparison-item" key={`${item}-${index}`} style={{ '--step': index }}><span>{index === 0 ? 'A' : index === 1 ? 'B' : index + 1}</span><strong>{item}</strong></div>)}
        </div>
      ) : type === 'network' ? (
        <div className="scene-network">
          <div className="network-center">{labels[0]}</div>
          <div className="network-branches">{labels.slice(1).map((item, index) => <div className="network-node" key={`${item}-${index}`} style={{ '--step': index }}>{item}</div>)}</div>
        </div>
      ) : type === 'applications' ? (
        <div className="scene-applications">{labels.map((item, index) => <div className="application-tile" key={`${item}-${index}`} style={{ '--step': index }}><span className="application-icon">{['✦', '◇', '◎', '↗', '▣'][index]}</span><strong>{item}</strong></div>)}</div>
      ) : (
        <div className="scene-concept">
          <div className="concept-orbit orbit-one" /><div className="concept-orbit orbit-two" />
          <div className="concept-core"><span>✦</span><strong>{labels[0]}</strong></div>
          <div className="concept-support">{labels.slice(1).map((item, index) => <span key={`${item}-${index}`} style={{ '--step': index }}>{item}</span>)}</div>
        </div>
      )}
      <div className="visual-scene-bottom">
        <div className="visual-moment-track" aria-label={`Visual ${momentNumber} of ${momentCount}`}>
          {Array.from({ length: momentCount }, (_, index) => <span key={index} className={index < momentNumber ? 'moment-complete' : ''} />)}
        </div>
        <div className="visual-scene-foot"><span className="scene-pulse" /> Scene {momentNumber} of {momentCount} · changes with the narration</div>
      </div>
    </section>
  );
}
