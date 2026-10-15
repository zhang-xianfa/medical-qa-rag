<script setup lang="ts">
import { computed } from 'vue'
import { useSessionStore } from '@/stores/sessionStore'
import { useMessageStore } from '@/stores/messageStore'
import { useAuthStore } from '@/stores/authStore'
import { fmtDate } from '@/utils/date'

const sessionStore = useSessionStore()
const msgStore = useMessageStore()
const authStore = useAuthStore()

const displayName = computed(() => authStore.user?.nickname || '用户')
const displayPhone = computed(() =>
  (authStore.user?.phone || '').replace(/(\d{3})\d{4}(\d{4})/, '$1****$2'),
)
const avatarChar = computed(() => (displayName.value || '用')[0])

const emit = defineEmits<{
  selectSession: [sid: string]
  deleteSession: [sid: string]
  newSession: []
  openProfile: []
}>()

function onDelete(sid: string, e: Event) {
  e.stopPropagation()
  if (msgStore.isLoading) return  // AI 思考中，禁止操作
  emit('deleteSession', sid)
}
</script>

<template>
  <aside class="flex flex-col w-72 flex-shrink-0 bg-eggplant-glass backdrop-blur-[10px] text-white/90 min-w-0">
    <!-- Brand -->
    <div class="flex items-center gap-2.5 px-5 py-5 border-b border-white/8">
      <div class="w-9 h-9 rounded-sm bg-wisteria flex items-center justify-center font-brand text-lg text-white flex-shrink-0">
        兰
      </div>
      <h1 class="font-brand text-lg tracking-wider text-white/95">灵兰健康</h1>
    </div>

    <!-- 新建会话 -->
    <button
      class="block w-[calc(100%-2rem)] mx-4 my-2 py-2 bg-wisteria rounded-sm text-sm font-medium text-white hover:bg-plum transition-colors font-sans text-center disabled:opacity-40 disabled:cursor-not-allowed"
      :disabled="msgStore.isLoading"
      @click="emit('newSession')"
    >
      + 新建会话
    </button>

    <!-- 会话列表 -->
    <div class="flex-1 overflow-y-auto py-1.5 chat-scroll">
      <p class="px-5 pt-2.5 pb-1 text-xs tracking-widest text-lilac">近期会话</p>
      <div
        v-for="s in sessionStore.sessions"
        :key="s.session_id"
        :class="[
          'flex items-center gap-2 px-5 py-2 transition-colors border-l-2 hover:bg-white/4',
          msgStore.isLoading ? 'pointer-events-none opacity-50' : 'cursor-pointer',
          sessionStore.currentSessionId === s.session_id
            ? 'bg-white/6 border-l-wisteria'
            : 'border-l-transparent',
        ]"
        @click="emit('selectSession', s.session_id)"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-blue flex-shrink-0" />
        <div class="flex-1 min-w-0">
          <div class="text-sm whitespace-nowrap overflow-hidden text-ellipsis">{{ s.title || '新会话' }}</div>
          <div class="text-xs text-lilac mt-0.5">{{ fmtDate(s.updated_at) }} · 第{{ s.round_count || 0 }}轮</div>
        </div>
        <button
          class="bg-none border-none text-lilac cursor-pointer text-sm opacity-0 hover:text-mauve transition-opacity hover:opacity-100"
          :class="{ 'opacity-100': sessionStore.currentSessionId === s.session_id }"
          @click="onDelete(s.session_id, $event)"
        >
          ×
        </button>
      </div>
    </div>

    <!-- 用户信息 -->
    <div class="p-4 border-t border-white/6">
      <div class="flex items-center gap-2.5 cursor-pointer" @click="emit('openProfile')">
        <div class="w-10 h-10 rounded-full bg-[#4a3d5a] flex items-center justify-center text-base flex-shrink-0">
          {{ avatarChar }}
        </div>
        <div>
          <div class="text-sm font-medium">{{ displayName }}</div>
          <div class="text-xs text-lilac mt-0.5">{{ displayPhone }}</div>
        </div>
      </div>
    </div>
  </aside>
</template>
