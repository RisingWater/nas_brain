import { useEffect, useRef, useState } from 'react';

export type AIFaceState = 'idle' | 'listening' | 'thinking' | 'operating' | 'speaking';

interface AIStatusFaceProps {
  state: AIFaceState;
  size?: number;
}

const STATE_COLORS: Record<AIFaceState, string> = {
  idle: '#7ec8e3',       // 青蓝
  listening: '#4fc3f7',  // 亮蓝 — 专注聆听
  thinking: '#ffb74d',   // 橙黄 — 思考
  operating: '#ff8a65',   // 珊瑚橙 — 操作
  speaking: '#81c784',   // 浅绿 — 说话
};

export default function AIStatusFace({ state, size = 300 }: AIStatusFaceProps) {
  const [blink, setBlink] = useState(false);
  const [prevState, setPrevState] = useState(state);
  const [animColor, setAnimColor] = useState(STATE_COLORS[state]);
  const [talkPhase, setTalkPhase] = useState(0);
  const blinkTimer = useRef<ReturnType<typeof setTimeout>>();
  const talkTimer = useRef<ReturnType<typeof setInterval>>();

  // State transition color animation
  useEffect(() => {
    if (prevState !== state) {
      setPrevState(state);
      setTimeout(() => setAnimColor(STATE_COLORS[state]), 10);
    } else {
      setAnimColor(STATE_COLORS[state]);
    }
  }, [state, prevState]);

  // Blinking — slow blink for idle, faster for others, no blink for listening
  useEffect(() => {
    const delay = state === 'idle' ? 3000 + Math.random() * 3000 : 4000 + Math.random() * 4000;
    const scheduleBlink = () => {
      blinkTimer.current = setTimeout(() => {
        setBlink(true);
        setTimeout(() => {
          setBlink(false);
          scheduleBlink();
        }, state === 'idle' ? 150 : 100);
      }, delay);
    };
    scheduleBlink();
    return () => { if (blinkTimer.current) clearTimeout(blinkTimer.current); };
  }, [state]);

  // Talking mouth animation
  useEffect(() => {
    if (state === 'speaking') {
      talkTimer.current = setInterval(() => {
        setTalkPhase(prev => (prev + 1) % 5);
      }, 140);
    } else {
      setTalkPhase(0);
      if (talkTimer.current) clearInterval(talkTimer.current);
    }
    return () => { if (talkTimer.current) clearInterval(talkTimer.current); };
  }, [state]);

  const color = animColor;
  const glowId = 'ai-face-glow';

  // ----- 眼睛 -----
  const eye = (side: 'left' | 'right') => {
    if (blink) return { x: side === 'left' ? 26 : 60, y: 39, w: 14, h: 2, rx: 1 };

    switch (state) {
      case 'listening':
        // 专注：大而圆的杏眼，略向内倾
        return { x: side === 'left' ? 24 : 58, y: 32, w: 18, h: 26, rx: 9 };
      case 'thinking':
        // 思考：眯眼上翻 — 窄而高
        return { x: side === 'left' ? 27 : 61, y: 33, w: 12, h: 12, rx: 6 };
      case 'operating':
        // 操作：锐利专注 — 方形眼略带角度
        return { x: side === 'left' ? 25 : 59, y: 36, w: 16, h: 14, rx: 3 };
      case 'speaking':
        // 说话：弯月眼
        return { x: side === 'left' ? 25 : 59, y: 36, w: 16, h: 18, rx: 8 };
      default: // idle
        return { x: side === 'left' ? 26 : 60, y: 37, w: 14, h: 18, rx: 7 };
    }
  };

  // ----- 眉毛 -----
  const brow = (side: 'left' | 'right') => {
    const baseY = 20;
    switch (state) {
      case 'listening':
        // 微抬，略呈八字（温和关注）
        return { y: baseY - 6, rotate: side === 'left' ? 5 : -5 };
      case 'thinking':
        // 紧锁 — 都向下内侧倾斜
        return { y: baseY + 4, rotate: side === 'left' ? 15 : -15 };
      case 'operating':
        // 用力集中 — 明显下压
        return { y: baseY + 6, rotate: side === 'left' ? 18 : -18 };
      case 'speaking':
        // 舒展微扬
        return { y: baseY - 4, rotate: side === 'left' ? -5 : 5 };
      default:
        return { y: baseY, rotate: 0 };
    }
  };

  // ----- 嘴巴 -----
  const mouth = () => {
    switch (state) {
      case 'listening':
        // 微张，像在认真听
        return <ellipse cx="50" cy="82" rx="6" ry="5" fill="none" stroke={color} strokeWidth="3" />;
      case 'thinking': {
        // 歪嘴 — 不对称
        return (
          <path
            d="M 36,82 Q 50,78 62,84"
            stroke={color} strokeWidth="3" fill="none" strokeLinecap="round"
          />
        );
      }
      case 'operating':
        // 紧抿 — 双横线，咬紧牙关的感觉
        return (
          <g>
            <path d="M 38,80 L 62,80" stroke={color} strokeWidth="3" fill="none" strokeLinecap="round" />
            <path d="M 42,85 L 58,85" stroke={color} strokeWidth="2.5" fill="none" strokeLinecap="round" />
          </g>
        );
      case 'speaking': {
        // 说话动画：开合
        const opens = [6, 9, 4, 7, 5];
        const ry = opens[talkPhase % opens.length];
        return (
          <ellipse
            cx="50" cy="82" rx="8" ry={ry}
            fill="none" stroke={color} strokeWidth="3"
          />
        );
      }
      default: // idle
        return (
          <path
            d="M 35,80 L 65,80"
            stroke={color} strokeWidth="3" fill="none" strokeLinecap="round"
          />
        );
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

        {/* 左眉 */}
        <rect
          x="23" y={lBrow.y} width="18" height="3" rx="1.5"
          fill={color}
          transform={`rotate(${lBrow.rotate}, 32, ${lBrow.y})`}
          style={{ transition: 'all 0.35s ease' }}
        />
        {/* 右眉 */}
        <rect
          x="59" y={rBrow.y} width="18" height="3" rx="1.5"
          fill={color}
          transform={`rotate(${rBrow.rotate}, 68, ${rBrow.y})`}
          style={{ transition: 'all 0.35s ease' }}
        />

        {/* 左眼 */}
        <rect
          x={lEye.x} y={lEye.y} width={lEye.w} height={lEye.h} rx={lEye.rx}
          fill={color}
          style={{ transition: 'all 0.2s ease' }}
        />
        {/* 右眼 */}
        <rect
          x={rEye.x} y={rEye.y} width={rEye.w} height={rEye.h} rx={rEye.rx}
          fill={color}
          style={{ transition: 'all 0.2s ease' }}
        />

        {/* 嘴 */}
        <g style={{ transition: 'all 0.3s ease' }} filter={`url(#${glowId})`}>
          {mouth()}
        </g>

        {/* 扫描线 */}
        <pattern id="ai-scan2" x="0" y="0" width="100" height="2" patternUnits="userSpaceOnUse">
          <rect x="0" y="0" width="100" height="1" fill="black" opacity={0.06} />
        </pattern>
        <rect x="0" y="0" width="100" height="100" fill="url(#ai-scan2)" style={{ mixBlendMode: 'overlay' }} />
      </svg>
    </div>
  );
}
