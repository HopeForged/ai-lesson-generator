import { Bot } from 'lucide-react';

/**
 * A compact SVG tutor. Arms are grouped at their shoulder pivots and the
 * mouth animates around its own centre, so neither can drift across the SVG.
 */
export default function TutorAvatar({ speaking, paused }) {
  const state = speaking && !paused ? 'tutor-speaking' : paused ? 'tutor-paused' : 'tutor-idle';

  return (
    <div className={`tutor-stage ${state}`}>
      <div className="tutor-stage-glow" />
      <svg
        className="tutor-character"
        viewBox="0 0 220 205"
        role="img"
        aria-label="Animated AI tutor"
      >
        <ellipse cx="110" cy="190" rx="62" ry="8" className="tutor-shadow" />

        {/* Arms are attached to the body and rotate around fixed shoulders. */}
        <g className="tutor-arm-group tutor-arm-left-group" transform="translate(72 139)">
          <g className="tutor-arm-swing">
            <path d="M0 0 C-16 5 -27 20 -28 37 C-28 44 -21 47 -16 41 L9 17 Z" className="tutor-arm" />
            <path d="M-28 36 C-39 31 -43 38 -38 46 C-33 52 -23 48 -17 42 Z" className="tutor-hand" />
          </g>
        </g>
        <g className="tutor-arm-group tutor-arm-right-group" transform="translate(148 139)">
          <g className="tutor-arm-swing">
            <path d="M0 0 C16 5 27 20 28 37 C28 44 21 47 16 41 L-9 17 Z" className="tutor-arm" />
            <path d="M28 36 C39 31 43 38 38 46 C33 52 23 48 17 42 Z" className="tutor-hand" />
          </g>
        </g>

        <path className="tutor-body" d="M61 184 Q64 128 110 126 Q156 128 159 184 Z" />
        <path className="tutor-shirt" d="M91 132 L110 151 L129 132 L143 184 L77 184 Z" />
        <path className="tutor-neck" d="M96 112 L124 112 L127 137 Q110 151 93 137 Z" />
        <path className="tutor-collar" d="M90 132 L110 151 L130 132" />
        <path className="tutor-tie" d="M110 151 L103 184 L117 184 Z" />

        <g className="tutor-head">
          <ellipse cx="110" cy="78" rx="48" ry="54" className="tutor-face" />
          <path className="tutor-hair" d="M63 77 Q55 26 103 22 Q155 15 160 69 Q143 47 124 47 Q99 62 63 77 Z" />
          <path className="tutor-hair-side" d="M63 69 Q53 91 70 111 L77 91 Z M157 67 Q169 92 151 111 L145 91 Z" />
          <circle cx="93" cy="81" r="4" className="tutor-eye" />
          <circle cx="127" cy="81" r="4" className="tutor-eye" />
          <path d="M103 96 Q110 101 117 96" className="tutor-smile" />
          <ellipse cx="110" cy="105" rx="7" ry="2" className="tutor-mouth" />
        </g>
      </svg>
      <div className="tutor-status">
        <Bot size={14} />
        {speaking && !paused ? 'AI tutor is teaching' : paused ? 'Lesson paused' : 'AI tutor is ready'}
      </div>
    </div>
  );
}
