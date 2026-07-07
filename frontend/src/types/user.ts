export interface User {
  user_id: string;
  display_name: string;
  user_type: string;
  wechat_name: string | null;
  is_temp: boolean;
  created_at: string | null;
  is_active: boolean | null;
}

export interface UserListData {
  total: number;
  users: User[];
  page: number;
  page_size: number;
}

export interface ApiResponse<T> {
  code: number;
  data: T;
  message: string;
}

export interface CreateUserPayload {
  display_name: string;
  user_type?: string;
  wechat_name?: string | null;
  is_temp?: boolean;
}

export interface UpdateUserPayload {
  display_name?: string | null;
  wechat_name?: string | null;
  is_temp?: boolean | null;
}
