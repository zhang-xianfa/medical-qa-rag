<script setup lang="ts">
import { computed } from 'vue'
import { Plus, MessageSquare, Trash2, X, Stethoscope } from 'lucide-vue-next'
import { useSessionStore } from '@/stores/sessionStore'
import { useMessageStore } from '@/stores/messageStore'
import { useAuthStore } from '@/stores/authStore'
import { fmtDate } from '@/utils/date'
import type { Session } from '@/types/session'

const props = withDefaults(defineProps<{ open?: boolean }>(), { open: true })

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
  close: []
}>()

function onDelete(sid: string, e: Event) {
  e.stopPropagation()
  if (msgStore.isLoading) return
  emit('deleteSession', sid)
}

function onSelect(sid: string) {
  emit('selectSession', sid)
  if (window.innerWidth < 768) emit('close')
}

/** 已结束的会话显示状态而不是轮数，避免出现「第 0 轮」这种怪东西 */
function statusText(s: Session): string {
  if (s.status === 'done') return '已完成'
  if (s.status === 'emergency_terminated') return '已终止'
  return `第${s.round_count || 0}轮`
}
</script>

<template>
  <!-- 移动端遮罩 -->
  <div
    v-if="props.open"
    class="fixed inset-0 z-30 bg-eggplant/40 backdrop-blur-[2px] md:hidden"
    @click="emit('close')"
  />

  <aside
    :class="[
      'sidebar-drawer fixed inset-y-0 left-0 z-40 flex flex-col w-72 flex-shrink-0',
      'bg-gradient-to-b from-[#2d2438] via-[#322840] to-[#3a2f47] text-white/90',
      'md:static md:z-auto md:translate-x-0',
      props.open ? 'translate-x-0' : '-translate-x-full',
    ]"
  >
    <!-- Brand -->
    <div class="flex items-center gap-3 px-5 pt-6 pb-5">
      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-wisteria to-plum flex items-center justify-center shadow-lg shadow-black/20 flex-shrink-0">
        <Stethoscope class="w-5 h-5 text-white" :stroke-width="1.8" />
      </div>
      <div class="min-w-0">
        <h1 class="font-brand text-lg tracking-[0.14em] text-white/95 leading-tight">灵兰健康</h1>
        <p class="text-[11px] text-lilac/80 tracking-wide">AI 智能问诊</p>
      </div>
      <button
        class="ml-auto md:hidden p-1.5 rounded-lg text-lilac hover:text-white hover:bg-white/10 transition-colors"
        aria-label="关闭侧边栏"
        @click="emit('close')"
      >
        <X class="w-[18px] h-[18px]" />
      </button>
    </div>

    <!-- 新建会话 -->
    <div class="px-4">
      <button
        class="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-wisteria/90 text-sm font-medium text-white shadow-lg shadow-black/10 hover:bg-wisteria active:scale-[0.99] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        :disabled="msgStore.isLoading"
        @click="emit('newSession')"
      >
        <Plus class="w-4 h-4" />
        新建会话
      </button>
    </div>

    <!-- 会话列表 -->
    <div class="flex-1 overflow-y-auto py-3 chat-scroll">
      <p class="px-5 pb-1.5 text-[11px] tracking-[0.18em] text-lilac/60">近期会话</p>

      <div v-if="sessionStore.sessions.length === 0" class="px-5 py-6 text-xs text-lilac/50 leading-relaxed">
        还没有会话记录<br />点击上方按钮开始第一次问诊
      </div>

      <div class="px-2 space-y-1">
        <div
          v-for="s in sessionStore.sessions"
          :key="s.session_id"
          :class="[
            'group flex items-center gap-2.5 px-3 py-2.5 rounded-xl transition-colors',
            msgStore.isLoading ? 'pointer-events-none opacity-50' : 'cursor-pointer',
            sessionStore.currentSessionId === s.session_id
              ? 'bg-white/10 text-white'
              : 'hover:bg-white/5',
          ]"
          @click="onSelect(s.session_id)"
        >
          <MessageSquare
            :class="[
              'w-4 h-4 flex-shrink-0 transition-colors',
              sessionStore.currentSessionId === s.session_id ? 'text-wisteria' : 'text-lilac/50',
            ]"
          />
          <div class="flex-1 min-w-0">
            <div class="text-[13px] whitespace-nowrap overflow-hidden text-ellipsis leading-snug">
              {{ s.title || '新会话' }}
            </div>
            <div class="text-[11px] text-lilac/55 mt-0.5">
              {{ fmtDate(s.updated_at) }} · {{ statusText(s) }}
            </div>
          </div>
          <button
            class="p-1 rounded-md text-lilac/40 opacity-0 group-hover:opacity-100 hover:text-rose hover:bg-white/10 transition-all"
            :class="{ 'opacity-100': sessionStore.currentSessionId === s.session_id }"
            aria-label="删除会话"
            @click="onDelete(s.session_id, $event)"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>

    <!-- 用户信息 -->
    <button
      class="flex items-center gap-3 mx-3 mb-4 px-3 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors text-left"
      @click="emit('openProfile')"
    >
      <div class="w-9 h-9 rounded-full bg-gradient-to-br from-mauve to-wisteria flex items-center justify-center text-sm font-medium text-white flex-shrink-0">
        {{ avatarChar }}
      </div>
      <div class="min-w-0">
        <div class="text-sm font-medium truncate">{{ displayName }}</div>
        <div class="text-[11px] text-lilac/60 mt-0.5">{{ displayPhone }}</div>
      </div>
    </button>
  </aside>
</template>
