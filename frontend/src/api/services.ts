import client from './client';
import type { ServicesResponse, ServiceActionResponse } from '../types/service';

export async function listServices(): Promise<ServicesResponse> {
  const res = await client.get<ServicesResponse>('/services');
  return res.data;
}

export async function startService(name: string): Promise<ServiceActionResponse> {
  const res = await client.post<ServiceActionResponse>(`/services/${name}/start`);
  return res.data;
}

export async function stopService(name: string): Promise<ServiceActionResponse> {
  const res = await client.post<ServiceActionResponse>(`/services/${name}/stop`);
  return res.data;
}
