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
  const [atBottom, setAtBottom] = useState(true);
  const polling = useRef<ReturnType<typeof setInterval>>();
  const scrollRef = useRef<HTMLDivElement>(null);

  // 加载文件列表
  useEffect(() => {
    listLogFiles().then((res) => {
      const fs = res.data;
      setFiles(fs);
      if (!selected && fs.length > 0) setSelected(fs[0].name);
    });
  }, []);

  // 判断是否在底部（距底 < 50px 视为在底部）
  const updateAtBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    setAtBottom(dist < 50);
  }, []);

  const scrollToBottom = useCallback((smooth = true) => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'instant' });
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

  // 新内容到达：仅在底部时自动滚
  useEffect(() => {
    if (atBottom) {
      scrollToBottom(false);
    }
  }, [lines]);

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

      <div style={{ position: 'relative', flex: 1 }}>
        <Card
          size="small"
          title={<Text style={{ fontSize: 13 }}>{selected || '未选择'} {total > 0 && `(${total} 行)`}</Text>}
          style={{ height: '100%', overflow: 'hidden' }}
          bodyStyle={{ padding: 0, height: 'calc(100% - 38px)', overflow: 'auto' }}
        >
          <div ref={scrollRef} onScroll={updateAtBottom} style={{ height: '100%', overflow: 'auto' }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
            ) : lines.length === 0 ? (
              <Empty description="暂无日志" style={{ padding: 40 }} />
            ) : (
              <div style={{ padding: '4px 0' }}>
                {lines.map((line, i) => renderLine(line, i))}
              </div>
            )}
          </div>
        </Card>

        {/* 不在底部时显示回底按钮 */}
        {!atBottom && (
          <Button
            type="primary"
            shape="circle"
            icon={<VerticalAlignBottomOutlined />}
            onClick={() => scrollToBottom(true)}
            style={{ position: 'absolute', bottom: 16, right: 16, zIndex: 10 }}
          />
        )}
      </div>
    </div>
  );
}
