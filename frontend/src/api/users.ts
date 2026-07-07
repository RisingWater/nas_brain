import client from './client';
import type {
  ApiResponse,
  UserListData,
  User,
  CreateUserPayload,
  UpdateUserPayload,
} from '../types/user';

export async function listUsers(params: {
  page?: number;
  page_size?: number;
  keyword?: string;
  user_type?: string;
  is_active?: boolean;
}): Promise<ApiResponse<UserListData>> {
  const res = await client.get<ApiResponse<UserListData>>('/admin/users', { params });
  return res.data;
}

export async function getUser(userId: string): Promise<ApiResponse<User>> {
  const res = await client.get<ApiResponse<User>>(`/admin/users/${userId}`);
  return res.data;
}

export async function createUser(
  data: CreateUserPayload,
): Promise<ApiResponse<{ success: boolean; user_id: string }>> {
  const res = await client.post<ApiResponse<{ success: boolean; user_id: string }>>(
    '/admin/users',
    data,
  );
  return res.data;
}

export async function updateUser(
  userId: string,
  data: UpdateUserPayload,
): Promise<ApiResponse<{ success: boolean; user_id: string }>> {
  const res = await client.put<ApiResponse<{ success: boolean; user_id: string }>>(
    `/admin/users/${userId}`,
    data,
  );
  return res.data;
}

export async function deleteUser(
  userId: string,
): Promise<ApiResponse<{ success: boolean; user_id: string }>> {
  const res = await client.delete<ApiResponse<{ success: boolean; user_id: string }>>(
    `/admin/users/${userId}`,
  );
  return res.data;
}
