<script setup lang="ts">
import { ref } from 'vue'
import { Stethoscope, ShieldCheck, Sparkles, HeartPulse } from 'lucide-vue-next'
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
  <div class="w-full h-full grid md:grid-cols-[1.05fr_1fr] overflow-y-auto chat-scroll">
    <!-- 左侧品牌区（移动端隐藏） -->
    <section class="relative hidden md:flex flex-col justify-between overflow-hidden bg-gradient-to-br from-[#2d2438] via-[#3a2c4b] to-[#4a3560] px-12 py-12 text-white">
      <!-- 装饰光斑 -->
      <div class="pointer-events-none absolute -top-24 -right-24 w-72 h-72 rounded-full bg-wisteria/25 blur-3xl" />
      <div class="pointer-events-none absolute bottom-0 -left-16 w-64 h-64 rounded-full bg-blue/20 blur-3xl" />

      <div class="relative flex items-center gap-3">
        <div class="w-11 h-11 rounded-2xl bg-white/10 backdrop-blur flex items-center justify-center border border-white/15">
          <Stethoscope class="w-5 h-5" :stroke-width="1.7" />
        </div>
        <div>
          <h1 class="font-brand text-xl tracking-[0.16em]">灵兰健康</h1>
          <p class="text-[11px] text-white/45 tracking-wider">AI 智能问诊</p>
        </div>
      </div>

      <div class="relative max-w-sm">
        <h2 class="font-brand text-3xl leading-snug tracking-wide">
          把症状说清楚，<br />让判断有依据
        </h2>
        <p class="mt-4 text-sm leading-7 text-white/60">
          基于医学知识库的分步问诊，逐项采集关键信息，给出结构化的症状分析与就医建议。
        </p>

        <ul class="mt-8 space-y-3.5 text-sm text-white/75">
          <li class="flex items-center gap-3">
            <Sparkles class="w-4 h-4 text-mauve" :stroke-width="1.8" />
            四阶段问诊：采集 → 专家分析 → 综合报告
          </li>
          <li class="flex items-center gap-3">
            <HeartPulse class="w-4 h-4 text-mauve" :stroke-width="1.8" />
            危险信号实时识别，先保安全再谈分析
          </li>
          <li class="flex items-center gap-3">
            <ShieldCheck class="w-4 h-4 text-mauve" :stroke-width="1.8" />
            身份证号、手机号等隐私信息自动脱敏
          </li>
        </ul>
      </div>

      <p class="relative text-[11px] text-white/30 leading-relaxed">
        本系统提供健康信息整理与参考建议，不构成医学诊断，<br />
        不能替代执业医师的面诊与检查。
      </p>
    </section>

    <!-- 右侧表单 -->
    <section class="flex items-center justify-center px-6 py-12 bg-mist">
      <div class="w-full max-w-sm">
        <!-- 移动端品牌 -->
        <div class="md:hidden flex items-center justify-center gap-2.5 mb-8">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-wisteria to-plum flex items-center justify-center">
            <Stethoscope class="w-5 h-5 text-white" :stroke-width="1.8" />
          </div>
          <h1 class="font-brand text-xl tracking-widest">灵兰健康</h1>
        </div>

        <h2 class="text-lg font-semibold text-eggplant/90">
          {{ activeTab === 'login' ? '欢迎回来' : '创建账号' }}
        </h2>
        <p class="mt-1 text-xs text-eggplant/45">
          {{ activeTab === 'login' ? '登录后继续您的问诊记录' : '注册后即可开始智能问诊' }}
        </p>

        <!-- Tabs -->
        <div class="flex mt-6 mb-6 p-1 rounded-xl bg-white border border-eggplant/8 shadow-soft">
          <button
            v-for="tab in (['login', 'register'] as const)"
            :key="tab"
            :class="[
              'flex-1 py-2 rounded-lg text-sm transition-all',
              activeTab === tab
                ? 'bg-gradient-to-br from-wisteria to-plum text-white font-medium shadow-soft'
                : 'text-eggplant/45 hover:text-eggplant/70',
            ]"
            @click="activeTab = tab; error = ''"
          >
            {{ tab === 'login' ? '登录' : '注册' }}
          </button>
        </div>

        <!-- Error -->
        <p v-if="error" class="text-rose text-xs mb-3 px-1">{{ error }}</p>

        <!-- Login -->
        <div v-if="activeTab === 'login'" class="space-y-4">
          <div>
            <label class="block text-xs text-eggplant/50 mb-1.5">手机号</label>
            <input
              v-model="loginPhone"
              type="tel"
              placeholder="请输入手机号"
              maxlength="20"
              class="w-full px-3.5 py-2.5 rounded-xl bg-white border border-eggplant/10 text-sm outline-none transition-all focus:border-wisteria/60 focus:shadow-soft font-sans"
              @keydown.enter="onLogin"
            />
          </div>
          <div>
            <label class="block text-xs text-eggplant/50 mb-1.5">密码</label>
            <input
              v-model="loginPw"
              type="password"
              placeholder="请输入密码"
              maxlength="128"
              class="w-full px-3.5 py-2.5 rounded-xl bg-white border border-eggplant/10 text-sm outline-none transition-all focus:border-wisteria/60 focus:shadow-soft font-sans"
              @keydown.enter="onLogin"
            />
          </div>
          <button
            :disabled="loading"
            class="w-full py-2.5 rounded-xl bg-gradient-to-br from-wisteria to-plum text-white text-sm font-medium transition-all hover:shadow-lg hover:shadow-wisteria/25 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            @click="onLogin"
          >
            {{ loading ? '登录中…' : '登录' }}
          </button>
        </div>

        <!-- Register -->
        <div v-if="activeTab === 'register'" class="space-y-4">
          <div>
            <label class="block text-xs text-eggplant/50 mb-1.5">手机号</label>
            <input
              v-model="regPhone"
              type="tel"
              placeholder="请输入手机号"
              maxlength="20"
              class="w-full px-3.5 py-2.5 rounded-xl bg-white border border-eggplant/10 text-sm outline-none transition-all focus:border-wisteria/60 focus:shadow-soft font-sans"
            />
          </div>
          <div>
            <label class="block text-xs text-eggplant/50 mb-1.5">密码（至少 6 位）</label>
            <input
              v-model="regPw"
              type="password"
              placeholder="请输入密码"
              maxlength="128"
              class="w-full px-3.5 py-2.5 rounded-xl bg-white border border-eggplant/10 text-sm outline-none transition-all focus:border-wisteria/60 focus:shadow-soft font-sans"
            />
          </div>
          <div>
            <label class="block text-xs text-eggplant/50 mb-1.5">昵称</label>
            <input
              v-model="regNick"
              type="text"
              placeholder="如何称呼您"
              maxlength="50"
              class="w-full px-3.5 py-2.5 rounded-xl bg-white border border-eggplant/10 text-sm outline-none transition-all focus:border-wisteria/60 focus:shadow-soft font-sans"
            />
          </div>
          <button
            :disabled="loading"
            class="w-full py-2.5 rounded-xl bg-gradient-to-br from-wisteria to-plum text-white text-sm font-medium transition-all hover:shadow-lg hover:shadow-wisteria/25 active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            @click="onRegister"
          >
            {{ loading ? '注册中…' : '注册' }}
          </button>
        </div>

        <p class="mt-6 text-center text-[11px] text-eggplant/30">
          继续即表示您理解：本系统不提供医学诊断，紧急情况请拨打 120
        </p>
      </div>
    </section>
  </div>
</template>
