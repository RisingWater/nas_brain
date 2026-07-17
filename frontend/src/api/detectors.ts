import client from './client';
import type { DetectorListResponse, DetectorActionResponse } from '../types/detector';

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
