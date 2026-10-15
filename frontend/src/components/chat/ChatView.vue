<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessageStore } from '@/stores/messageStore'
import { useSessionStore } from '@/stores/sessionStore'
import { useScroll } from '@/composables/useScroll'
import ChatMessage from './ChatMessage.vue'
import ThinkingIndicator from './ThinkingIndicator.vue'

const msgStore = useMessageStore()
const sessionStore = useSessionStore()

const containerRef = ref<HTMLElement | null>(null)
const { onScroll, scrollToBottom } = useScroll(containerRef)

// 诊断完成后禁用选项
const isDiagnosisDone = computed(() => msgStore.isDiagnosisDone)

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
  if (msgStore.isLoading) return true   // AI 思考中，禁用所有选项
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
    class="chat-scroll flex-1 w-full max-w-3xl overflow-y-auto px-4 py-4 flex flex-col gap-3.5"
    @scroll="onScroll"
  >
    <!-- 空状态欢迎 -->
    <div
      v-if="msgStore.messages.length === 0 && !msgStore.isLoading"
      class="flex-1 flex flex-col items-center justify-center gap-3 text-text-secondary"
    >
      <h2 class="font-brand text-3xl font-bold text-eggplant">灵兰健康</h2>
      <p class="text-lg font-semibold">描述您的症状，AI 将为您逐步分析</p>
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
