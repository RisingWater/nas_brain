export interface Schedule {
  id: number;
  creator_id: string;
  content: string;
  rtype: string;
  rdatetime: string | null;
  lunar: boolean;
  strategy: string;
  prompt: string | null;
  notify_type: string;
  notify_target: string | null;
  done: boolean;
  created_at: string;
}

export interface ScheduleListResponse {
  code: number;
  data: {
    total: number;
    schedules: Schedule[];
    page: number;
    page_size: number;
  };
  message: string;
}

export interface ScheduleActionResponse {
  code: number;
  data: unknown;
  message: string;
}
