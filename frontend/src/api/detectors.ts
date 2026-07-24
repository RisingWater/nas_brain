import client from './client';
import type { DetectorListResponse, DetectorActionResponse, DetectorConfigResponse, DetectorConfigSchemaResponse } from '../types/detector';

export async function listDetectors(): Promise<DetectorListResponse> {
  const res = await client.get<DetectorListResponse>('/detectors');
  return res.data;
}

export async function reloadDetectors(): Promise<DetectorActionResponse> {
  const res = await client.post<DetectorActionResponse>('/detectors/reload');
  return res.data;
}

export async function enableDetector(name: string, enable: boolean): Promise<void> {
  await client.put(`/detectors/${name}/enable`, { enable });
}

export async function getDetectorConfigSchema(name: string): Promise<DetectorConfigSchemaResponse> {
  const res = await client.get<DetectorConfigSchemaResponse>(`/detectors/${name}/config-schema`);
  return res.data;
}

export async function getDetectorConfig(name: string): Promise<DetectorConfigResponse> {
  const res = await client.get<DetectorConfigResponse>(`/detectors/${name}/config`);
  return res.data;
}

export async function saveDetectorConfig(name: string, config: Record<string, any>): Promise<void> {
  await client.put(`/detectors/${name}/config`, config);
}
