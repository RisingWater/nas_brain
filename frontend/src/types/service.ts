export interface ServiceInfo {
  name: string;
  command: string;
  description: string;
  enable: boolean;
  status: 'running' | 'stopped' | 'disabled' | string;
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
