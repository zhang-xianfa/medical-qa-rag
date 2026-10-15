<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const auth = useAuthStore()

const activeTab = ref<'login' | 'register'>('login')
const error = ref('')

// Login fields
const loginPhone = ref('')
const loginPw = ref('')

// Register fields
const regPhone = ref('')
const regPw = ref('')
const regNick = ref('')

const loading = ref(false)

async function onLogin() {
  error.value = ''
  if (!loginPhone.value.trim() || !loginPw.value) {
    error.value = '请填写手机号和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(loginPhone.value.trim(), loginPw.value)
  } catch {
    error.value = '手机号或密码错误'
  } finally {
    loading.value = false
  }
}

async function onRegister() {
  error.value = ''
  if (!regPhone.value.trim() || !regPw.value || !regNick.value.trim()) {
    error.value = '请填写所有字段'
    return
  }
  loading.value = true
  try {
    await auth.register(regPhone.value.trim(), regPw.value, regNick.value.trim())
  } catch {
    error.value = '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="w-full h-full flex items-center justify-center bg-lavender">
    <div class="w-[min(24rem,90vw)] bg-white rounded-lg p-10 shadow-elevated">
      <!-- Brand -->
      <div class="flex items-center justify-center gap-2 mb-8">
        <div class="w-9 h-9 rounded-sm bg-wisteria flex items-center justify-center font-brand text-xl text-white">
          兰
        </div>
        <h1 class="font-brand text-xl tracking-wider">灵兰健康</h1>
      </div>

      <!-- Tabs -->
      <div class="flex border-b-2 border-lilac-light mb-6">
        <button
          :class="[
            'flex-1 py-2 text-center text-sm cursor-pointer transition-colors border-b-2 -mb-0.5 font-sans',
            activeTab === 'login'
              ? 'text-wisteria border-wisteria font-medium'
              : 'text-text-secondary border-transparent',
          ]"
          @click="activeTab = 'login'; error = ''"
        >
          登录
        </button>
        <button
          :class="[
            'flex-1 py-2 text-center text-sm cursor-pointer transition-colors border-b-2 -mb-0.5 font-sans',
            activeTab === 'register'
              ? 'text-wisteria border-wisteria font-medium'
              : 'text-text-secondary border-transparent',
          ]"
          @click="activeTab = 'register'; error = ''"
        >
          注册
        </button>
      </div>

      <!-- Error -->
      <p v-if="error" class="text-mauve text-xs text-center mb-2">{{ error }}</p>

      <!-- Login Form -->
      <div v-if="activeTab === 'login'">
        <div class="mb-4">
          <label class="block text-xs text-text-secondary mb-1">手机号</label>
          <input
            v-model="loginPhone"
            type="tel"
            placeholder="请输入手机号"
            maxlength="20"
            class="w-full px-3 py-2.5 border-1.5 border-lilac-light rounded-md text-sm outline-none transition-colors focus:border-wisteria font-sans"
            @keydown.enter="onLogin"
          />
        </div>
        <div class="mb-4">
          <label class="block text-xs text-text-secondary mb-1">密码</label>
          <input
            v-model="loginPw"
            type="password"
            placeholder="请输入密码"
            maxlength="128"
            class="w-full px-3 py-2.5 border-1.5 border-lilac-light rounded-md text-sm outline-none transition-colors focus:border-wisteria font-sans"
            @keydown.enter="onLogin"
          />
        </div>
        <button
          :disabled="loading"
          class="w-full py-2.5 bg-wisteria text-white rounded-md text-sm font-medium cursor-pointer transition-colors hover:bg-plum disabled:opacity-60 disabled:cursor-not-allowed mt-2 font-sans"
          @click="onLogin"
        >
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </div>

      <!-- Register Form -->
      <div v-if="activeTab === 'register'">
        <div class="mb-4">
          <label class="block text-xs text-text-secondary mb-1">手机号</label>
          <input
            v-model="regPhone"
            type="tel"
            placeholder="请输入手机号"
            maxlength="20"
            class="w-full px-3 py-2.5 border-1.5 border-lilac-light rounded-md text-sm outline-none transition-colors focus:border-wisteria font-sans"
          />
        </div>
        <div class="mb-4">
          <label class="block text-xs text-text-secondary mb-1">密码（至少6位）</label>
          <input
            v-model="regPw"
            type="password"
            placeholder="请输入密码"
            maxlength="128"
            class="w-full px-3 py-2.5 border-1.5 border-lilac-light rounded-md text-sm outline-none transition-colors focus:border-wisteria font-sans"
          />
        </div>
        <div class="mb-4">
          <label class="block text-xs text-text-secondary mb-1">昵称</label>
          <input
            v-model="regNick"
            type="text"
            placeholder="如何称呼您"
            maxlength="50"
            class="w-full px-3 py-2.5 border-1.5 border-lilac-light rounded-md text-sm outline-none transition-colors focus:border-wisteria font-sans"
          />
        </div>
        <button
          :disabled="loading"
          class="w-full py-2.5 bg-wisteria text-white rounded-md text-sm font-medium cursor-pointer transition-colors hover:bg-plum disabled:opacity-60 disabled:cursor-not-allowed mt-2 font-sans"
          @click="onRegister"
        >
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </div>
    </div>
  </div>
</template>
