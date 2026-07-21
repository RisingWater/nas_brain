import { useEffect, useState, useCallback } from 'react';
import { Space, Button, Spin } from 'antd';
import {
  SyncOutlined, BugOutlined, ClockCircleOutlined, UserOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import AIStatusFace, { type AIFaceState } from '../components/AIStatusFace';
import { getAIStatus, setAIStatus, connectAIStatusWS } from '../api/status';
import type { AIStatus } from '../api/status';

// Check URL for debug mode
const isDebug = new URLSearchParams(window.location.search).has('debug');
const rotateDeg = parseInt(new URLSearchParams(window.location.search).get('rotate') || '0', 10);

const STATES: { key: AIFaceState; label: string; color: string }[] = [
  { key: 'idle', label: '空闲', color: '#7ec8e3' },
  { key: 'listening', label: '聆听', color: '#ffaa00' },
  { key: 'thinking', label: '思考', color: '#ffdd44' },
  { key: 'operating', label: '操作', color: '#ff9933' },
  { key: 'speaking', label: '说话', color: '#44dd66' },
];

const STATE_DESCRIPTIONS: Record<AIFaceState, string> = {
  idle: '等待输入中',
  listening: '检测到唤醒词，正在录音识别',
  thinking: '大脑正在思考如何处理',
  operating: '正在调用工具执行操作',
  speaking: '正在输出回复',
};

// 空闲时轮流显示的小提示
const IDLE_TIPS = [
  '💡 试试对我说 "今天天气怎么样？"',
  '🔍 我可以帮你查资料、搜网页',
  '🎵 我可以语音播报新闻和提醒',
  '📝 我可以帮你记录备忘录',
  '🔌 我可以控制家里的智能设备',
  '⏰ 说 "提醒我半小时后关火" 设置提醒',
  '📚 我可以帮你查考试成绩',
  '🗣️ 在群里 @我 也能和我对话',
  '🎯 我会记住你说过的重要信息',
  '⚡ 连续说两次 "派蒙" 唤醒我即可对话',
];

export default function AIStatusPage() {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [debugState, setDebugState] = useState<AIFaceState | null>(null);
  const [idleTipIndex, setIdleTipIndex] = useState(0);

  const faceState: AIFaceState = debugState ?? (status?.state as AIFaceState) ?? 'idle';

  const fetchStatus = useCallback(async () => {
    try {
      const data = await getAIStatus();
      setStatus(data);
    } catch {
      // keep old state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // WebSocket 实时推送（主通道）
    const closeWS = connectAIStatusWS(
      (data) => {
        setStatus(data);
        setLoading(false);
      },
      () => {
        // WebSocket 断开，依赖轮询兜底
        console.log('AI Status WebSocket 断开，回退到轮询');
      },
    );

    // 初始获取 + 5s 轮询兜底
    fetchStatus();
    const timer = setInterval(fetchStatus, 5000);

    return () => {
      closeWS();
      clearInterval(timer);
    };
  }, [fetchStatus]);

  // 空闲时轮流显示小提示
  useEffect(() => {
    if (faceState !== 'idle') return;
    const timer = setInterval(() => {
      setIdleTipIndex((i) => (i + 1) % IDLE_TIPS.length);
    }, 6000);
    return () => clearInterval(timer);
  }, [faceState]);
  const curSpeaker = status?.speaker ?? '';
  const curDuration = status?.duration ?? 0;
  const uptime = (status?.extra?.uptime_seconds as number) || 0;

  const handleDebugSet = async (state: string) => {
    setDebugState(state as AIFaceState);
    try {
      await setAIStatus(state);
    } catch {
      // ignore
    }
  };

  const handleDebugReset = () => {
    setDebugState(null);
    fetchStatus();
  };

  // Find current state display info
  const curStateInfo = STATES.find(s => s.key === faceState) ?? STATES[0];

  if (loading) {
    return (
      <div style={{
        position: 'fixed', inset: 0,
        display: 'flex', justifyContent: 'center', alignItems: 'center',
        background: '#0a0a0f',
      }}>
        <Spin size="large" />
      </div>
    );
  }

  const pageContent = (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'radial-gradient(ellipse at center, #14141f 0%, #0a0a0f 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      overflow: 'hidden',
      userSelect: 'none',
    }}>
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '16px 24px',
      }}>
        <a
          href="/"
          style={{ color: 'rgba(255,255,255,0.4)', fontSize: 13, textDecoration: 'none' }}
          onMouseOver={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.7)')}
          onMouseOut={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
        >
          <ArrowLeftOutlined style={{ marginRight: 6 }} />
          管理后台
        </a>
        <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: 12, letterSpacing: 1 }}>
          NAS Brain
        </span>
      </div>
<div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: -40,
      }}>
        <AIStatusFace state={faceState} size={Math.min(window.innerWidth * 0.6, window.innerHeight * 0.5, 400)} />

        {/* State label */}
        <div style={{
          marginTop: 24,
          fontSize: 28,
          fontWeight: 300,
          color: curStateInfo.color,
          letterSpacing: 2,
          textShadow: `0 0 20px ${curStateInfo.color}40`,
          transition: 'all 0.5s ease',
        }}>
          {curStateInfo.label}
        </div>
        <div style={{
          marginTop: 8,
          fontSize: 14,
          color: 'rgba(255,255,255,0.35)',
          transition: 'all 0.3s ease',
        }}>
          {STATE_DESCRIPTIONS[faceState]}
        </div>
        {/* 上下文文字 / 空闲小提示 */}
        {faceState === 'idle' ? (
          <div style={{
            marginTop: 6,
            fontSize: 20,
            color: curStateInfo.color,
            opacity: 0.5,
            textAlign: 'center',
            maxWidth: 400,
            lineHeight: 1.6,
            transition: 'all 0.5s ease',
            animation: 'fadeInOut 6s ease infinite',
          }}>
            {IDLE_TIPS[idleTipIndex]}
          </div>
        ) : status?.message ? (
          <div style={{
            marginTop: 10,
            fontSize: 20,
            color: curStateInfo.color,
            opacity: 0.7,
            textAlign: 'center',
            maxWidth: 400,
            lineHeight: 1.5,
            textShadow: `0 0 10px ${curStateInfo.color}30`,
            transition: 'all 0.3s ease',
          }}>
            {status.message}
          </div>
        ) : null}
      </div>
<div style={{
        position: 'absolute', bottom: 0, left: 0, right: 0,
        display: 'flex', justifyContent: 'center', gap: 24,
        padding: '20px 24px',
        flexWrap: 'wrap',
      }}>
        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>
          <SyncOutlined spin={faceState !== 'idle'} style={{ marginRight: 4 }} />
          持续 {curDuration.toFixed(1)} 秒
        </span>
        {curSpeaker && (
          <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>
            <UserOutlined style={{ marginRight: 4 }} />
            {curSpeaker}
          </span>
        )}
        <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: 12 }}>
          <ClockCircleOutlined style={{ marginRight: 4 }} />
          运行 {Math.floor(uptime / 86400)}天{Math.floor((uptime % 86400) / 3600)}时
        </span>
      </div>

      {/* Debug overlay */}
      {isDebug && (
        <div style={{
          position: 'absolute', bottom: 80, left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(8px)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 12,
          padding: '12px 16px',
        }}>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 8, textAlign: 'center' }}>
            <BugOutlined style={{ marginRight: 4 }} />调试面板
          </div>
          <Space wrap style={{ justifyContent: 'center', display: 'flex' }}>
            {STATES.map(s => (
              <Button
                key={s.key}
                size="small"
                type={faceState === s.key ? 'primary' : 'default'}
                style={{
                  ...(faceState === s.key ? { backgroundColor: s.color, borderColor: s.color, color: '#000' } : {}),
                  fontSize: 12,
                }}
                onClick={() => handleDebugSet(s.key)}
              >
                {s.label}
              </Button>
            ))}
            <Button size="small" onClick={handleDebugReset} style={{ fontSize: 12 }}>
              恢复实时
            </Button>
          </Space>
          <div style={{ marginTop: 6, fontSize: 11, color: 'rgba(255,255,255,0.25)', textAlign: 'center' }}>
            当前：{faceState} | 实时：{status?.state ?? '-'}
          </div>
        </div>
      )}
    </div>
  );

  return rotateDeg ? (
    <div style={{ position: 'fixed', inset: 0, overflow: 'hidden' }}>
      <div style={{
        position: 'absolute',
        width: '100vh',
        height: '100vw',
        top: '50%',
        left: '50%',
        transform: `translate(-50%, -50%) rotate(${rotateDeg}deg)`,
      }}>
        {pageContent}
      </div>
    </div>
  ) : pageContent;
}
