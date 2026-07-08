import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Select, Card, Row, Col, Input, Switch, Typography, Tag, Space, Empty, Spin, Button,
} from 'antd';
import { ReloadOutlined, SearchOutlined, VerticalAlignBottomOutlined } from '@ant-design/icons';
import type { LogFile } from '../types/log';
import { listLogFiles, readLog } from '../api/logs';

const { Text } = Typography;
const POLL_INTERVAL = 3000;

const LEVEL_COLORS: Record<string, string> = {
  INFO: 'blue',
  WARNING: 'orange',
  ERROR: 'red',
  DEBUG: 'default',
};

export default function LogViewer() {
  const [files, setFiles] = useState<LogFile[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [lines, setLines] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [level, setLevel] = useState<string | undefined>(undefined);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [showBottomBtn, setShowBottomBtn] = useState(false);

  const polling = useRef<ReturnType<typeof setInterval>>();
  const containerRef = useRef<HTMLDivElement>(null);

  // 加载文件列表
  useEffect(() => {
    listLogFiles().then((res) => {
      const fs = res.data;
      setFiles(fs);
      if (!selected && fs.length > 0) setSelected(fs[0].name);
    });
  }, []);

  const fetchLog = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    try {
      const res = await readLog(selected, { lines: 500, keyword: keyword || undefined, level });
      setLines(res.data.lines);
      setTotal(res.data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [selected, keyword, level]);

  useEffect(() => {
    fetchLog();
  }, [fetchLog]);

  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      polling.current = setInterval(fetchLog, POLL_INTERVAL);
    } else {
      clearInterval(polling.current);
    }
    return () => clearInterval(polling.current);
  }, [autoRefresh, fetchLog]);

  // 滚动到底部
  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    setShowBottomBtn(false);
  }, []);

  // 内容变化时，如果在底部则自动滚
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (dist < 50) {
      el.scrollTop = el.scrollHeight;
      setShowBottomBtn(false);
    } else {
      setShowBottomBtn(true);
    }
  }, [lines]);

  // 监听手动滚动
  const onScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowBottomBtn(dist >= 50);
  }, []);

  const renderLine = (line: string, i: number) => {
    let tag: string | null = null;
    for (const lv of ['ERROR', 'WARNING', 'INFO', 'DEBUG']) {
      if (line.includes(lv)) { tag = lv; break; }
    }
    const color = tag ? LEVEL_COLORS[tag] : undefined;

    return (
      <div key={i} style={{
        fontFamily: 'monospace', fontSize: 12, lineHeight: '20px',
        whiteSpace: 'pre-wrap', wordBreak: 'break-all',
        background: i % 2 === 0 ? '#fafafa' : 'transparent',
        padding: '0 8px',
      }}>
        {tag && <Tag color={color} style={{ fontSize: 10, marginRight: 4, lineHeight: '16px' }}>{tag}</Tag>}
        <Text style={{ fontSize: 12 }}>{line}</Text>
      </div>
    );
  };

  return (
    <div style={{ height: 'calc(100vh - 120px)', display: 'flex', flexDirection: 'column' }}>
      <Row gutter={[8, 8]} style={{ marginBottom: 8 }}>
        <Col xs={24} sm={12} md={6}>
          <Select
            style={{ width: '100%' }}
            value={selected || undefined}
            placeholder="选择日志文件"
            onChange={(v) => { setSelected(v); setKeyword(''); }}
            options={files.map((f) => ({
              label: `${f.name} (${(f.size / 1024).toFixed(1)} KB)`,
              value: f.name,
            }))}
          />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Input
            placeholder="搜索关键词"
            prefix={<SearchOutlined />}
            allowClear
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => fetchLog()}
          />
        </Col>
        <Col xs={12} sm={6} md={3}>
          <Select
            style={{ width: '100%' }}
            placeholder="级别"
            allowClear
            value={level}
            onChange={setLevel}
            options={[
              { label: '全部', value: undefined },
              { label: 'ERROR', value: 'ERROR' },
              { label: 'WARNING', value: 'WARNING' },
              { label: 'INFO', value: 'INFO' },
              { label: 'DEBUG', value: 'DEBUG' },
            ]}
          />
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>自动刷新</Text>
            <Switch checked={autoRefresh} onChange={setAutoRefresh} size="small" />
            <ReloadOutlined onClick={fetchLog} style={{ cursor: 'pointer' }} />
          </Space>
        </Col>
      </Row>

      <Card
        size="small"
        title={<Text style={{ fontSize: 13 }}>{selected}{total > 0 ? ` (${total} 行)` : ''}</Text>}
        style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, minHeight: 0, padding: 0, position: 'relative', overflow: 'hidden' }}
      >
        <div
          ref={containerRef}
          onScroll={onScroll}
          style={{ height: '100%', overflowY: 'auto' }}
        >
          {loading && lines.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : lines.length === 0 ? (
            <Empty description="暂无日志" style={{ padding: 40 }} />
          ) : (
            <div style={{ padding: '4px 0' }}>
              {lines.map((line, i) => renderLine(line, i))}
            </div>
          )}
        </div>

        {showBottomBtn && (
          <Button
            type="primary"
            shape="circle"
            icon={<VerticalAlignBottomOutlined />}
            onClick={scrollToBottom}
            style={{ position: 'absolute', bottom: 16, right: 16, zIndex: 10 }}
          />
        )}
      </Card>
    </div>
  );
}
