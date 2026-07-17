export interface DetectorInfo {
  name: string;
  interval: number;
  class: string;
  enable: boolean;
}

export interface DetectorListResponse {
  code: number;
  data: DetectorInfo[];
  message: string;
}

export interface DetectorActionResponse {
  code: number;
  data: { loaded?: number; reloaded?: number; total: number };
  message: string;
}
