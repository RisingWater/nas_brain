export interface ProcessorInfo {
  name: string;
  description: string;
  priority: number;
  class: string;
}

export interface ProcessorListResponse {
  code: number;
  data: ProcessorInfo[];
  message: string;
}

export interface ProcessorActionResponse {
  code: number;
  data: { loaded?: number; reloaded?: number; total: number };
  message: string;
}
