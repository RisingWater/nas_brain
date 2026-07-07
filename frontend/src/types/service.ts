export interface ServiceInfo {
  name: string;
  command: string;
  description: string;
  status: 'running' | 'stopped' | string;
  pid: number | null;
}

export interface ServicesResponse {
  code: number;
  data: ServiceInfo[];
  message: string;
}

export interface ServiceActionResponse {
  code: number;
  message: string;
}
