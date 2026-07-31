export interface PostgresConfig {
  host: string
  port: number
  user: string
  password: string | null
  database: string
}

export interface RedisConfig {
  host: string
  port: number
  password: string | null
  db: number
}

export interface MinioConfig {
  endpoint: string
  access_key: string
  secret_key: string | null
  bucket: string
  secure: boolean
}

export interface RuntimeSettingsInput {
  postgres: PostgresConfig
  redis: RedisConfig
  minio: MinioConfig
}

export interface ComponentHealth {
  ok: boolean
  message: string | null
}

export type RuntimeHealthMap = {
  postgres: ComponentHealth
  redis: ComponentHealth
  minio: ComponentHealth
}

export interface RuntimeSettingsRead extends RuntimeSettingsInput {
  health: RuntimeHealthMap
  config_file: string
}
