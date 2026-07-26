import client from './client';

export interface RssArticle {
  title: string;
  pubDate: string;
  link: string;
  guid: string;
  description: string;
  tags: string[];
  feed_name: string;
  _tag: string;
}

export interface RssKnowledgeResponse {
  total: number;
  limit: number;
  offset: number;
  items: RssArticle[];
}

export async function getRssKnowledge(params: {
  tag?: string;
  feed?: string;
  limit?: number;
  offset?: number;
}): Promise<RssKnowledgeResponse> {
  const { data } = await client.get('/admin/rss-knowledge', { params });
  return data;
}

export async function getRssFeeds(): Promise<string[]> {
  const { data } = await client.get('/admin/rss-knowledge/feeds');
  return data.feeds;
}

export async function getRssTags(): Promise<string[]> {
  const { data } = await client.get('/admin/rss-knowledge/tags');
  return data.tags;
}
