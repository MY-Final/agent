<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DocumentChecked, Lock, User } from '@element-plus/icons-vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { getErrorMessage } from '@/api/client'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = reactive({ username: '', password: '' })
const submitting = ref(false)

const rules: FormRules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const changeFormRef = ref<FormInstance>()
const changeVisible = ref(false)
const changing = ref(false)
const changeForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const changeRules: FormRules = {
  oldPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码长度至少 6 位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== changeForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

function redirectAfterLogin(): void {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  const target = redirect.startsWith('/') ? redirect : '/'
  void router.replace(target)
}

async function submit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const mustChange = await auth.login({
      username: form.username.trim(),
      password: form.password,
    })
    if (mustChange) {
      changeForm.oldPassword = form.password
      changeForm.newPassword = ''
      changeForm.confirmPassword = ''
      changeVisible.value = true
    } else {
      redirectAfterLogin()
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function submitChangePassword(): Promise<void> {
  const valid = await changeFormRef.value?.validate().catch(() => false)
  if (!valid) return
  changing.value = true
  try {
    await authApi.changePassword({
      old_password: changeForm.oldPassword,
      new_password: changeForm.newPassword,
    })
    auth.mustChangePassword = false
    changeVisible.value = false
    ElMessage.success('密码修改成功')
    redirectAfterLogin()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    changing.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <span class="login-brand-mark">
          <el-icon><DocumentChecked /></el-icon>
        </span>
        <div>
          <h1>投标分析 Agent</h1>
          <p>登录后使用任务、模板与资质分析工作台</p>
        </div>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="submit"
      >
        <el-form-item label="账号" prop="username">
          <el-input
            v-model="form.username"
            :prefix-icon="User"
            placeholder="请输入账号"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :prefix-icon="Lock"
            placeholder="请输入密码"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        <el-button type="primary" class="login-submit" :loading="submitting" @click="submit">
          登 录
        </el-button>
      </el-form>
    </div>

    <el-dialog
      v-model="changeVisible"
      title="首次登录请修改管理员密码"
      width="460px"
      align-center
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="出于安全考虑"
        description="当前使用初始密码登录，请设置新密码后再进入系统。此操作不可跳过。"
      />
      <el-form
        ref="changeFormRef"
        :model="changeForm"
        :rules="changeRules"
        label-position="top"
        class="change-form"
        @keyup.enter="submitChangePassword"
      >
        <el-form-item label="当前密码" prop="oldPassword">
          <el-input
            v-model="changeForm.oldPassword"
            type="password"
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input
            v-model="changeForm.newPassword"
            type="password"
            :prefix-icon="Lock"
            placeholder="至少 6 位"
            autocomplete="new-password"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input
            v-model="changeForm.confirmPassword"
            type="password"
            autocomplete="new-password"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="changing" @click="submitChangePassword">
          确认修改
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background: var(--app-background);
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 34px 34px 30px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  background: var(--surface-color);
  box-shadow: 0 10px 34px rgba(31, 41, 36, 0.08);
}

.login-brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 26px;
}

.login-brand-mark {
  display: grid;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 10px;
  background: var(--primary-color);
  color: white;
  font-size: 22px;
}

.login-brand h1 {
  margin: 0;
  color: var(--text-primary);
  font-size: 18px;
}

.login-brand p {
  margin: 5px 0 0;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 1.6;
}

.login-submit {
  width: 100%;
  height: 40px;
  margin-top: 6px;
}

.change-form {
  margin-top: 16px;
}
</style>
