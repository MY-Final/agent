<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '@/components/AppShell.vue'

const route = useRoute()
// 公开页面（登录页）不渲染侧边栏工作台外壳，避免暴露业务内容
const showShell = computed(() => !route.meta.public)
</script>

<template>
  <AppShell v-if="showShell">
    <router-view />
  </AppShell>
  <router-view v-else />
</template>
