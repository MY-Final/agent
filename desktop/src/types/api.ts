export interface ApiResponse<T> {
  code: number
  msg: string
  data: T | null
}

export interface HealthData {
  status: 'healthy' | 'unhealthy' | string
  postgres: 'up' | 'down' | string
  redis: 'up' | 'down' | string
  minio: 'up' | 'down' | string
}
