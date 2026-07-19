import { useEffect, useRef, useState } from 'react';

export type AIFaceState = 'idle' | 'listening' | 'thinking' | 'operating' | 'speaking';

interface AIStatusFaceProps {
  state: AIFaceState;
  size?: number;
}

const STATE_COLORS: Record<AIFaceState, string> = {
  idle: '#7ec8e3',
  listening: '#ffaa00',
  thinking: '#ffb74d',
  operating: '#ff8a65',
  speaking: '#81c784',
};

// 所有状态统一的眼睛/眉毛高度（参考思考位）
const EYE_Y = 50;
const BROW_Y = 38;

function LoadingSpinner({ color }: { color: string }) {
  return (
    <g transform="translate(50, 53)">
      <g>
        <circle cx="0" cy="0" r="42" fill="none" stroke={color} strokeWidth="3.5"
          strokeDasharray="22 242" strokeLinecap="round" opacity="0.5">
          <animateTransform attributeName="transform" type="rotate"
            from="0" to="360" dur="1.2s" repeatCount="indefinite" />
        </circle>
      </g>
      <g transform="rotate(120)">
        <circle cx="0" cy="0" r="42" fill="none" stroke={color} strokeWidth="3.5"
          strokeDasharray="22 242" strokeLinecap="round" opacity="0.5">
          <animateTransform attributeName="transform" type="rotate"
            from="0" to="360" dur="1.2s" repeatCount="indefinite" />
        </circle>
      </g>
      <g transform="rotate(240)">
        <circle cx="0" cy="0" r="42" fill="none" stroke={color} strokeWidth="3.5"
          strokeDasharray="22 242" strokeLinecap="round" opacity="0.5">
          <animateTransform attributeName="transform" type="rotate"
            from="0" to="360" dur="1.2s" repeatCount="indefinite" />
        </circle>
      </g>
    </g>
  );
}

export default function AIStatusFace({ state, size = 300 }: AIStatusFaceProps) {
  const [blink, setBlink] = useState(false);
  const [browTwitch, setBrowTwitch] = useState(false);
  const [prevState, setPrevState] = useState(state);
  const [animColor, setAnimColor] = useState(STATE_COLORS[state]);
  const blinkTimer = useRef<ReturnType<typeof setTimeout>>();
  const twitchTimer = useRef<ReturnType<typeof setTimeout>>();

  // State transition color animation
  useEffect(() => {
    if (prevState !== state) {
      setPrevState(state);
      setTimeout(() => setAnimColor(STATE_COLORS[state]), 10);
    } else {
      setAnimColor(STATE_COLORS[state]);
    }
  }, [state, prevState]);

  // Blinking
  useEffect(() => {
    const delay = 3000 + Math.random() * 4000;
    const scheduleBlink = () => {
      blinkTimer.current = setTimeout(() => {
        setBlink(true);
        setTimeout(() => {
          setBlink(false);
          scheduleBlink();
        }, 120);
      }, delay);
    };
    scheduleBlink();
    return () => { if (blinkTimer.current) clearTimeout(blinkTimer.current); };
  }, []);

  // Right eyebrow random twitch
  useEffect(() => {
    const scheduleTwitch = () => {
      const delay = 4000 + Math.random() * 6000;
      twitchTimer.current = setTimeout(() => {
        setBrowTwitch(true);
        setTimeout(() => {
          setBrowTwitch(false);
          scheduleTwitch();
        }, 800 + Math.random() * 600);
      }, delay);
    };
    scheduleTwitch();
    return () => { if (twitchTimer.current) clearTimeout(twitchTimer.current); };
  }, []);

  const color = animColor;

  // ----- 眼睛 -----
  const eye = (side: 'left' | 'right') => {
    if (blink) return { x: side === 'left' ? 26 : 60, y: EYE_Y + 2, w: 14, h: 2, rx: 1, rotate: 0 };

    switch (state) {
      case 'listening':
        return { x: side === 'left' ? 24 : 58, y: EYE_Y, w: 18, h: 26, rx: 9, rotate: 0 };
      case 'thinking':
        return { x: side === 'left' ? 25 : 59, y: EYE_Y, w: 16, h: 18, rx: 8, rotate: side === 'left' ? -12 : 12 };
      case 'operating':
        return { x: side === 'left' ? 25 : 59, y: EYE_Y, w: 16, h: 14, rx: 3, rotate: 0 };
      case 'speaking':
        return { x: side === 'left' ? 25 : 59, y: EYE_Y, w: 16, h: 18, rx: 8, rotate: 0 };
      default: // idle
        return { x: side === 'left' ? 26 : 60, y: EYE_Y, w: 14, h: 18, rx: 7, rotate: 0 };
    }
  };

  // ----- 眉毛 -----
  const brow = (side: 'left' | 'right') => {
    switch (state) {
      case 'listening':
        return { y: BROW_Y, rotate: side === 'left' ? 5 : -5 };
      case 'thinking':
        return { y: BROW_Y, rotate: side === 'left' ? 15 : -15 };
      case 'operating':
        return { y: BROW_Y, rotate: side === 'left' ? 18 : -18 };
      case 'speaking':
        return { y: BROW_Y, rotate: side === 'left' ? -5 : 5 };
      default: // idle
        return { y: BROW_Y, rotate: 0 };
    }
  };

  const lEye = eye('left');
  const rEye = eye('right');
  const lBrow = brow('left');
  const rBrow = brow('right');

  return (
    <div style={{
      width: size,
      height: size,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      filter: `drop-shadow(0 0 20px ${color}50)`,
      transition: 'filter 0.6s ease',
    }}>
      <svg viewBox="-8 -8 116 116" width="100%" height="100%" style={{ display: 'block' }}>
        <defs>
          <filter id="ai-face-glow" filterUnits="userSpaceOnUse" x="-10" y="-10" width="120" height="120">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* 左眉 */}
        <rect
          x="23" y={lBrow.y} width="18" height="3" rx="1.5"
          fill={color}
          transform={`rotate(${lBrow.rotate}, 32, ${lBrow.y})`}
          style={{ transition: 'all 0.35s ease' }}
        />
        {/* 右眉（偶尔自己翘起来） */}
        <rect
          x="59" y={rBrow.y} width="18" height="3" rx="1.5"
          fill={color}
          transform={`rotate(${rBrow.rotate + (browTwitch ? -18 : 0)}, 68, ${rBrow.y})`}
          style={{ transition: 'all 0.35s ease' }}
        />

        {/* 左眼 */}
        <g style={{ transition: 'all 0.3s ease' }}>
          <rect
            x={lEye.x} y={lEye.y} width={lEye.w} height={lEye.h} rx={lEye.rx}
            fill={color}
            transform={lEye.rotate ? `rotate(${lEye.rotate}, ${lEye.x + lEye.w / 2}, ${lEye.y + lEye.h / 2})` : undefined}
          />
        </g>
        <g style={{ transition: 'all 0.3s ease' }}>
          <rect
            x={rEye.x} y={rEye.y} width={rEye.w} height={rEye.h} rx={rEye.rx}
            fill={color}
            transform={rEye.rotate ? `rotate(${rEye.rotate}, ${rEye.x + rEye.w / 2}, ${rEye.y + rEye.h / 2})` : undefined}
          />
        </g>

        {/* 旋转 loading（思考 / 操作） */}
        {(state === 'thinking' || state === 'operating') && (
          <LoadingSpinner color={color} />
        )}

        {/* 聆听：脉冲圈 — 收缩淡出 */}
        {state === 'listening' && (
          <g transform="translate(50, 53)">
            <circle cx="0" cy="0" r="47" fill="none" stroke={color} strokeWidth="3" opacity="0.35">
              <animate attributeName="r" values="47;37" dur="1.2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.35;0" dur="1.2s" repeatCount="indefinite" />
            </circle>
            <circle cx="0" cy="0" r="47" fill="none" stroke={color} strokeWidth="2.5" opacity="0.25">
              <animate attributeName="r" values="47;37" dur="1.8s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.25;0" dur="1.8s" repeatCount="indefinite" />
            </circle>
          </g>
        )}

        {/* 说话：脉冲圈 — 从小到大扩散 */}
        {state === 'speaking' && (
          <g transform="translate(50, 53)">
            <circle cx="0" cy="0" r="37" fill="none" stroke={color} strokeWidth="3" opacity="0">
              <animate attributeName="r" values="37;47" dur="1.2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0;0.35" dur="1.2s" repeatCount="indefinite" />
            </circle>
            <circle cx="0" cy="0" r="37" fill="none" stroke={color} strokeWidth="2.5" opacity="0">
              <animate attributeName="r" values="37;47" dur="1.8s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0;0.25" dur="1.8s" repeatCount="indefinite" />
            </circle>
          </g>
        )}

        {/* 扫描线 */}
        <pattern id="ai-scan3" x="0" y="0" width="100" height="2" patternUnits="userSpaceOnUse">
          <rect x="0" y="0" width="100" height="1" fill="black" opacity={0.06} />
        </pattern>
        <rect x="0" y="0" width="100" height="100" fill="url(#ai-scan3)" style={{ mixBlendMode: 'overlay' }} />
      </svg>
    </div>
  );
}
