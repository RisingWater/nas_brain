import { useEffect, useState } from 'react';
import {
  Card, Select, Typography, Spin, Tag, Space, Empty, Pagination, Row, Col,
} from 'antd';
import { getRssKnowledge, getRssFeeds, getRssTags } from '../api/rssKnowledge';
import type { RssArticle } from '../api/rssKnowledge';

const { Text, Paragraph } = Typography;
const PAGE_SIZE = 20;

function formatDate(pubDate: string) {
  if (!pubDate) return '-';
  const d = new Date(pubDate);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

const tagColors: Record<string, string> = {
  '股市财经': 'red',
  '时政要闻': 'blue',
};

export default function RssKnowledgePage() {
  const [articles, setArticles] = useState<RssArticle[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [tags, setTags] = useState<string[]>([]);
  const [feeds, setFeeds] = useState<string[]>([]);
  const [filterTag, setFilterTag] = useState<string | undefined>();
  const [filterFeed, setFilterFeed] = useState<string | undefined>();

  useEffect(() => {
    getRssTags().then(setTags).catch(() => {});
    getRssFeeds().then(setFeeds).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    getRssKnowledge({
      tag: filterTag,
      feed: filterFeed,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }).then((res) => {
      setArticles(res.items);
      setTotal(res.total);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [page, filterTag, filterFeed]);

  return (
    <div>
      {/* 筛选栏 */}
      <Row gutter={12} style={{ marginBottom: 16 }} align="middle">
        <Col>
          <Text strong style={{ fontSize: 16 }}>实时知识</Text>
        </Col>
        <Col flex="160px">
          <Select
            style={{ width: '100%' }}
            placeholder="全部标签"
            allowClear
            value={filterTag}
            onChange={(v) => { setFilterTag(v); setPage(1); }}
            options={tags.map((t) => ({ label: t, value: t }))}
          />
        </Col>
        <Col flex="160px">
          <Select
            style={{ width: '100%' }}
            placeholder="全部来源"
            allowClear
            value={filterFeed}
            onChange={(v) => { setFilterFeed(v); setPage(1); }}
            options={feeds.map((f) => ({ label: f, value: f }))}
          />
        </Col>
        <Col>
          <Text type="secondary">共 {total} 条</Text>
        </Col>
      </Row>

      {/* 列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : articles.length === 0 ? (
        <Empty description="暂无内容" />
      ) : (
        <>
          {articles.map((item, idx) => (
            <Card
              key={item.guid || idx}
              size="small"
              style={{ marginBottom: 8 }}
              hoverable
              onClick={() => item.link && window.open(item.link, '_blank')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <Space size={4}>
                  {item._tag && (
                    <Tag color={tagColors[item._tag] || 'default'} style={{ marginRight: 4 }}>{item._tag}</Tag>
                  )}
                  <Text strong>{item.title || '(无标题)'}</Text>
                </Space>
                <Space size={12}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{item.feed_name}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{formatDate(item.pubDate)}</Text>
                </Space>
              </div>
              {item.description && (
                <Paragraph
                  ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                  style={{ margin: 0, fontSize: 13, color: '#666' }}
                >
                  {item.description}
                </Paragraph>
              )}
            </Card>
          ))}
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Pagination
              current={page}
              total={total}
              pageSize={PAGE_SIZE}
              onChange={(p) => setPage(p)}
              showTotal={(t) => `共 ${t} 条`}
              size="small"
            />
          </div>
        </>
      )}
    </div>
  );
}
