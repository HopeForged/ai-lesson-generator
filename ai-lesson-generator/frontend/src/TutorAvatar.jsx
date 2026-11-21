import './lecturer.css';

const ACTION_LABELS = {
  explain: 'Explaining',
  point_left: 'Pointing to the board',
  point_right: 'Pointing to the board',
  emphasize: 'Making a key point',
  welcome: 'Welcoming the class',
};

/**
 * A friendly, human-proportioned lecturer standing behind a lectern.
 * Every limb is built from simple rounded strokes so proportions stay clean,
 * and each arm has a shoulder and an elbow joint so gestures look natural.
 * The pose is chosen with a CSS class (pose-explain, pose-point, ...).
 */
function Arm({ side }) {
  // Left = the arm on the viewer's left (closest to the teaching board).
  const left = side === 'left';
  const sx = left ? 92 : 228;          // shoulder x
  const ex = left ? 88 : 232;          // elbow x
  return (
    <g className={`arm arm-${side}`} style={{ transformOrigin: `${sx}px 246px` }}>
      <line className="sleeve" x1={sx} y1="246" x2={ex} y2="312" />
      <g className="forearm" style={{ transformOrigin: `${ex}px 312px` }}>
        <line className="sleeve" x1={ex} y1="312" x2={ex} y2="368" />
        <line className="cuff" x1={ex} y1="360" x2={ex} y2="368" />
        <line className="finger" x1={ex} y1="378" x2={ex} y2="404" />
        <ellipse className="hand" cx={ex} cy="380" rx="13" ry="15" />
        <ellipse className="thumb" cx={left ? ex + 11 : ex - 11} cy="376" rx="4.5" ry="9" transform={`rotate(${left ? -18 : 18} ${left ? ex + 11 : ex - 11} 376)`} />
      </g>
    </g>
  );
}

export default function TutorAvatar({ speaking, paused, action = 'explain', caption, look = 'mensah', mouth = null }) {
  const safe = ACTION_LABELS[action] ? action : 'explain';
  const pose = !speaking ? 'idle' : safe.startsWith('point') ? 'point' : safe;
  const state = speaking && !paused ? 'is-speaking' : paused ? 'is-paused' : 'is-idle';
  const label = speaking && !paused ? ACTION_LABELS[safe] : paused ? 'Paused' : 'Ready to teach';

  return (
    <div className={`lecturer look-${look} ${state} pose-${pose} ${mouth !== null ? 'mouth-driven' : ''}`} style={mouth !== null ? { '--mouth': mouth } : undefined}>
      <svg className="lecturer-svg" viewBox="0 0 320 400" role="img" aria-label="A friendly lecturer standing at a lectern">
        <g className="body-sway">
          <path className="hair-back" d="M108 100 C96 150 98 216 120 240 L200 240 C222 216 224 150 212 100Z" />
          {/* neck + torso */}
          <path className="skin" d="M143 150 L143 214 Q160 232 177 214 L177 150Z" />
          <path className="skin-shade" d="M143 168 Q160 192 177 168 L177 150 L143 150Z" />
          <path className="jacket" d="M52 400 L52 280 C52 250 72 234 108 224 L141 212 L160 250 L179 212 L212 224 C248 234 268 250 268 280 L268 400Z" />
          <path className="shirt" d="M141 208 L160 280 L179 208 L170 200 L160 214 L150 200Z" />
          <path className="collar" d="M141 204 L158 222 L148 232 L132 210Z M179 204 L162 222 L172 232 L188 210Z" />
          <path className="lapel" d="M141 212 L160 288 L146 300 L108 226Z M179 212 L160 288 L174 300 L212 226Z" />
          <path className="tie" d="M153 232 L167 232 L164 244 L170 300 L160 312 L150 300 L156 244Z" />
          <path className="pocket" d="M196 276 L226 274" />
          <Arm side="left" />
          <Arm side="right" />

          {/* head */}
          <g className="head">
            <ellipse className="skin" cx="116" cy="106" rx="7" ry="13" />
            <ellipse className="skin" cx="204" cy="106" rx="7" ry="13" />
            <path className="skin" d="M118 102 C118 64 138 48 160 48 C182 48 202 64 202 102 C202 134 188 164 160 170 C132 164 118 134 118 102Z" />
            <path className="hair hair-f" d="M112 108 C104 56 128 30 162 30 C196 30 218 56 208 108 C206 90 198 74 186 66 C172 70 150 68 142 54 C134 70 122 84 118 96 C114 100 113 104 112 108Z" />
            <path className="hair hair-m" d="M114 104 C108 60 130 32 162 32 C194 32 214 58 206 104 C203 88 198 78 190 72 C178 66 160 66 148 56 C140 66 132 72 125 80 C118 86 116 94 114 104Z" />
            <path className="hair-light" d="M132 58 C148 44 176 44 194 58" />
            <ellipse className="blush" cx="132" cy="128" rx="9" ry="5" />
            <ellipse className="blush" cx="188" cy="128" rx="9" ry="5" />
            <path className="brow" d="M130 91 Q143 85 156 90" />
            <path className="brow" d="M164 90 Q177 85 190 91" />
            <g className="eyes">
              <ellipse className="eye-white" cx="143" cy="104" rx="7" ry="4.6" />
              <ellipse className="eye-white" cx="177" cy="104" rx="7" ry="4.6" />
              <circle className="iris" cx="143.5" cy="104.4" r="3.5" />
              <circle className="iris" cx="177.5" cy="104.4" r="3.5" />
              <circle className="glint" cx="144.6" cy="103.2" r="1.1" />
              <circle className="glint" cx="178.6" cy="103.2" r="1.1" />
            </g>
            <g className="glasses">
              <rect x="128" y="94" width="30" height="22" rx="8" />
              <rect x="162" y="94" width="30" height="22" rx="8" />
              <path d="M158 102 Q160 99 162 102" />
              <path d="M128 100 L119 98 M192 100 L201 98" />
            </g>
            <path className="nose" d="M160 110 C158 120 154 127 154 130 C158 134 162 134 166 130" />
            <path className="mouth-closed" d="M147 146 Q160 156 173 146" />
            <g className="mouth-open">
              <path d="M150 144 Q160 142 170 144 Q169 155 160 156 Q151 155 150 144Z" className="mouth-inner" />
              <path d="M152 144 Q160 143 168 144 L167 147 Q160 146 153 147Z" className="teeth" />
            </g>
          </g>

          {/* lectern in front of the lower body */}
        </g>
        <g className="lectern">
          <path className="lectern-body" d="M60 336 L260 336 L270 400 L50 400Z" />
          <rect className="lectern-top" x="40" y="322" width="240" height="16" rx="5" />
          <rect className="lectern-notes" x="132" y="306" width="62" height="18" rx="2" />
          <path className="lectern-line" d="M142 312 L184 312 M142 317 L172 317" />
          <circle className="lectern-badge" cx="160" cy="368" r="11" />
        </g>
      </svg>
      <div className="lecturer-caption"><span className="live-dot" />{caption || label}</div>
    </div>
  );
}
