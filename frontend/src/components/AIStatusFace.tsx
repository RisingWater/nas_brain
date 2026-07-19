import { useEffect, useRef, useState } from 'react';

export type AIFaceState = 'idle' | 'listening' | 'thinking' | 'operating' | 'speaking';

interface AIStatusFaceProps {
  state: AIFaceState;
  size?: number;
}

const STATE_COLORS: Record<AIFaceState, string> = {
  idle: '#7ec8e3',       // 青蓝
  listening: '#ffaa00',  // 橙黄 — 警觉
  thinking: '#ffdd44',   // 亮黄 — 思考
  operating: '#ff9933',  // 橙 — 操作中
  speaking: '#44dd66',   // 绿 — 说话
};

const STATE_LABELS: Record<AIFaceState, string> = {
  idle: '空闲中',
  listening: '正在聆听...',
  thinking: '思考中...',
  operating: '操作中...',
  speaking: '说话中...',
};

export default function AIStatusFace({ state, size = 300 }: AIStatusFaceProps) {
  const [blink, setBlink] = useState(false);
  const [prevState, setPrevState] = useState(state);
  const [animColor, setAnimColor] = useState(STATE_COLORS[state]);
  const [talkPhase, setTalkPhase] = useState(0);
  const blinkTimer = useRef<ReturnType<typeof setTimeout>>();
  const talkTimer = useRef<ReturnType<typeof setInterval>>();
  const colorTimer = useRef<ReturnType<typeof setTimeout>>();

  // State transition color animation
  useEffect(() => {
    if (prevState !== state) {
      setPrevState(state);
      // Smooth color transition via CSS transition
      setTimeout(() => setAnimColor(STATE_COLORS[state]), 10);
    } else {
      setAnimColor(STATE_COLORS[state]);
    }
  }, [state, prevState]);

  // Blinking
  useEffect(() => {
    const scheduleBlink = () => {
      blinkTimer.current = setTimeout(() => {
        setBlink(true);
        setTimeout(() => {
          setBlink(false);
          scheduleBlink();
        }, 120);
      }, 2000 + Math.random() * 3000);
    };
    scheduleBlink();
    return () => { if (blinkTimer.current) clearTimeout(blinkTimer.current); };
  }, []);

  // Talking mouth animation
  useEffect(() => {
    if (state === 'speaking') {
      talkTimer.current = setInterval(() => {
        setTalkPhase(prev => (prev + 1) % 4);
      }, 180);
    } else {
      setTalkPhase(0);
      if (talkTimer.current) clearInterval(talkTimer.current);
    }
    return () => { if (talkTimer.current) clearInterval(talkTimer.current); };
  }, [state]);

  const color = animColor;
  const glowId = 'ai-face-glow';

  // Eye shape per state
  const eye = (side: 'left' | 'right') => {
    if (blink) return { ry: 1, h: 2, y: 40, rx: 7 };

    switch (state) {
      case 'listening':
        return { ry: 16, h: 32, y: 34, rx: 7 }; // Wide alert eyes
      case 'thinking':
        if (side === 'left') return { ry: 3, h: 6, y: 40, rx: 7 }; // Squinting
        return { ry: 12, h: 24, y: 38, rx: 7 };
      case 'operating':
        if (side === 'left') return { ry: 10, h: 20, y: 38, rx: 7 };
        return { ry: 4, h: 8, y: 40, rx: 7 }; // Mismatched
      case 'speaking':
        return { ry: 10, h: 20, y: 36, rx: 7 }; // Happy arches
      default: // idle
        return { ry: 10, h: 20, y: 38, rx: 7 };
    }
  };

  // Eyebrow per state
  const brow = (side: 'left' | 'right') => {
    const bY = 20;
    switch (state) {
      case 'listening':
        return { y: bY - 10, rotate: 0 }; // Raised
      case 'thinking':
        if (side === 'left') return { y: bY, rotate: 0 };
        return { y: bY - 5, rotate: 15 }; // One raised
      case 'operating':
        if (side === 'left') return { y: bY - 5, rotate: -15 };
        return { y: bY + 3, rotate: 15 }; // Conflicted
      case 'speaking':
        return { y: bY - 5, rotate: side === 'left' ? -8 : 8 };
      default:
        return { y: bY, rotate: 0 };
    }
  };

  // Mouth per state
  const mouth = () => {
    switch (state) {
      case 'listening':
        return <ellipse cx="50" cy="80" rx="5" ry="6" fill="none" stroke={color} strokeWidth="3" />; // Small O
      case 'speaking': {
        // Talking mouth: oscillate between smile and open
        const open = [1, 0.3, 0.7, 0.5][talkPhase];
        return (
          <ellipse
            cx="50" cy="80" rx="8" ry={4 + open * 4}
            fill="none" stroke={color} strokeWidth="3"
          />
        );
      }
      case 'thinking':
        return <path d="M 38,80 L 62,80" stroke={color} strokeWidth="3" strokeLinecap="round" />;
      case 'operating':
        return <path d="M 38,82 Q 50,76 62,83" stroke={color} strokeWidth="3" strokeLinecap="round" />; // Quirky
      default: // idle
        return <path d="M 35,78 L 65,78" stroke={color} strokeWidth="3" strokeLinecap="round" />;
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
      filter: `drop-shadow(0 0 18px ${color}40)`,
      transition: 'filter 0.6s ease',
    }}>
      <svg viewBox="0 0 100 100" width="100%" height="100%" style={{ display: 'block' }}>
        <defs>
          <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Left eyebrow */}
        <rect
          x="24" y={lBrow.y} width="18" height="3" rx="1.5"
          fill={color}
          transform={`rotate(${lBrow.rotate}, 33, ${lBrow.y})`}
          style={{ transition: 'all 0.4s ease' }}
        />
        {/* Right eyebrow */}
        <rect
          x="58" y={rBrow.y} width="18" height="3" rx="1.5"
          fill={color}
          transform={`rotate(${rBrow.rotate}, 67, ${rBrow.y})`}
          style={{ transition: 'all 0.4s ease' }}
        />

        {/* Left eye */}
        <rect
          x={26} y={lEye.y - lEye.h / 2}
          width="14" height={lEye.h} rx={lEye.rx}
          fill={color}
          style={{ transition: 'all 0.2s ease' }}
        />
        {/* Right eye */}
        <rect
          x={60} y={rEye.y - rEye.h / 2}
          width="14" height={rEye.h} rx={rEye.rx}
          fill={color}
          style={{ transition: 'all 0.2s ease' }}
        />

        {/* Mouth */}
        <g style={{ transition: 'all 0.3s ease' }} filter={`url(#${glowId})`}>
          {mouth()}
        </g>

        {/* Scanline overlay */}
        <pattern id="ai-scan" x="0" y="0" width="100" height="2" patternUnits="userSpaceOnUse">
          <rect x="0" y="0" width="100" height="1" fill="black" opacity={0.06} />
        </pattern>
        <rect x="0" y="0" width="100" height="100" fill="url(#ai-scan)" style={{ mixBlendMode: 'overlay' }} />
      </svg>
    </div>
  );
}
