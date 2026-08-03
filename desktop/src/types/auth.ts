export interface LoginResult {
  token: string
  username: string
  must_change_password: boolean
}

export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}
