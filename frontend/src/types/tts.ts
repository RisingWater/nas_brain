export interface TtsCacheEntry {
  id: string;
  text: string;
  text_full: string;
  backend: string;
  filename: string;
  size: number;
  size_str: string;
  created_at: number;
  created_at_str: string;
  last_access: number;
  last_access_str: string;
  hit_count: number;
  file_exists: boolean;
}

export interface TtsCacheListResponse {
  code: number;
  data: TtsCacheEntry[];
  message: string;
}

export interface TtsCacheStats {
  total_entries: number;
  valid_entries: number;
  total_size: number;
  total_size_str: string;
}

export interface TtsCacheStatsResponse {
  code: number;
  data: TtsCacheStats;
  message: string;
}

export interface TtsCacheActionResponse {
  code: number;
  data: unknown;
  message: string;
}
