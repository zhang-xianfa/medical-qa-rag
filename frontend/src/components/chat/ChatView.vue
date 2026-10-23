<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Stethoscope, ArrowUpRight, ShieldCheck } from 'lucide-vue-next'
import { useMessageStore } from '@/stores/messageStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useScroll } from '@/composables/useScroll'
import ChatMessage from './ChatMessage.vue'
import ThinkingIndicator from './ThinkingIndicator.vue'

const emit = defineEmits<{ quickAsk: [text: string] }>()

const msgStore = useMessageStore()
const sessionStore = useSessionStore()

const containerRef = ref<HTMLElement | null>(null)
const { onScroll, scrollToBottom } = useScroll(containerRef)

const isDiagnosisDone = computed(() => msgStore.isDiagnosisDone)

const quickPrompts = [
  { label: '头痛三天，有点发烧', text: '我头痛三天了，还有点发烧' },
  { label: '咳嗽、咽痛', text: '我咳嗽两天了，嗓子疼' },
  { label: '肚子疼、拉肚子', text: '我肚子疼，还拉肚子' },
  { label: '睡不着、压力大', text: '最近总是睡不着，工作压力很大' },
]

// 找到最后一条含选项的 assistant 消息的索引
// 只有这条消息的选项可点击，历史选项全部禁用
const lastActiveChoiceIndex = computed(() => {
  const msgs = msgStore.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && (msgs[i].options?.length ?? 0) > 0) {
      return i
    }
  }
  return -1
})

/** 判断某条消息的选项是否应禁用 */
function isChoiceDisabled(msgIndex: number): boolean {
  if (msgStore.isLoading) return true
  if (isDiagnosisDone.value) return true
  if (lastActiveChoiceIndex.value === -1) return false
  return msgIndex !== lastActiveChoiceIndex.value
}

// 新消息到来时滚动到底部
watch(
  () => msgStore.messages.length,
  () => scrollToBottom(),
)

function onSelectChoice(value: string, label: string) {
  if (!sessionStore.currentSessionId) return
  msgStore.sendChoice(value, label, sessionStore.currentSessionId)
}
</script>

<template>
  <div
    ref="containerRef"
    class="chat-scroll flex-1 w-full max-w-3xl overflow-y-auto px-4 py-6 flex flex-col gap-4"
    aria-live="polite"
    aria-label="问诊对话"
    @scroll="onScroll"
  >
    <!-- 空状态 -->
    <div
      v-if="msgStore.messages.length === 0 && !msgStore.isLoading"
      class="flex-1 flex flex-col items-center justify-center max-w-lg mx-auto text-center animate-fade-up"
    >
      <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-wisteria to-plum flex items-center justify-center shadow-float mb-5">
        <Stethoscope class="w-7 h-7 text-white" :stroke-width="1.6" />
      </div>

      <h2 class="font-brand text-2xl font-bold text-eggplant tracking-wide">你好，我是灵兰</h2>
      <p class="mt-2 text-sm text-eggplant/55 leading-relaxed">
        用几句话描述您的不适，我会一步步追问关键信息，<br class="hidden sm:block" />
        最后给出症状分析和就医建议。
      </p>

      <div class="mt-7 grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full">
        <button
          v-for="q in quickPrompts"
          :key="q.label"
          class="group flex items-center justify-between gap-2 px-4 py-3 rounded-xl bg-white border border-eggplant/8 text-left text-sm text-eggplant/75 shadow-soft hover:border-wisteria/40 hover:shadow-float hover:-translate-y-0.5 transition-all"
          @click="emit('quickAsk', q.text)"
        >
          <span>{{ q.label }}</span>
          <ArrowUpRight class="w-4 h-4 text-eggplant/25 group-hover:text-wisteria transition-colors" />
        </button>
      </div>

      <p class="mt-6 flex items-center gap-1.5 text-[11px] text-eggplant/35">
        <ShieldCheck class="w-3.5 h-3.5" />
        仅供健康参考，不能替代医生诊断；紧急情况请立即拨打 120
      </p>
    </div>

    <!-- 消息列表 -->
    <ChatMessage
      v-for="(msg, idx) in msgStore.messages"
      :key="msg.id"
      :message="msg"
      :disabled-choices="isChoiceDisabled(idx)"
      @select-choice="onSelectChoice"
    />

    <!-- 思考指示器 -->
    <ThinkingIndicator v-if="msgStore.isLoading" />
  </div>
</template>
