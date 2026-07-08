export interface LogFile {
  name: string;
  size: number;
  mtime: number;
}

export interface LogData {
  filename: string;
  total: number;
  lines: string[];
  offset: number;
  returned: number;
}

export interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}
