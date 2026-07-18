import client from './client';

export interface BackupItem {
  filename: string;
  size: number;
  created_at: string;
}

export async function createBackup(): Promise<{ success: boolean; filename: string; size: number }> {
  const res = await client.post('/admin/backup/create');
  return res.data;
}

export async function listBackups(): Promise<{ items: BackupItem[] }> {
  const res = await client.get('/admin/backup/list');
  return res.data;
}

export function getDownloadUrl(filename: string): string {
  return `/api/admin/backup/download/${encodeURIComponent(filename)}`;
}

export async function deleteBackup(filename: string): Promise<{ success: boolean }> {
  const res = await client.delete(`/admin/backup/${encodeURIComponent(filename)}`);
  return res.data;
}
