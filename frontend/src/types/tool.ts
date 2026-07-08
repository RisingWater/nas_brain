export interface ToolInfo {
  name: string;
  description: string;
  silent: boolean;
  final: boolean;
  parameters: Record<string, unknown>;
}

export interface ToolsResponse {
  code: number;
  data: ToolInfo[];
  message: string;
}

export interface ToolActionResponse {
  code: number;
  data: { loaded?: number; reloaded?: number; total: number };
  message: string;
}
