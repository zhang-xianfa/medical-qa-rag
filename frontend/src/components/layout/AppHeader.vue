<script setup lang="ts">
import { computed } from 'vue'
import { useMessageStore } from '@/stores/messageStore'

const msgStore = useMessageStore()

const stageLabel = computed(() => {
  if (msgStore.isDiagnosisDone) return '诊断报告'
  if (msgStore.messages.length > 0) return '问诊中'
  return ''
})

const roundCount = computed(() => {
  const last = msgStore.messages.filter(m => m.round_number > 0).pop()
  return last?.round_number ?? 0
})
</script>

<template>
  <div class="w-full max-w-3xl px-4 py-3 flex items-center gap-2.5">
    <span
      v-if="stageLabel"
      class="stage-badge text-xs font-medium px-2.5 py-0.5 rounded-full"
      :class="msgStore.isDiagnosisDone ? 'bg-blue/10 text-blue-dark' : 'bg-wisteria-ghost text-wisteria'"
    >
      {{ stageLabel }}
    </span>
    <span class="ml-auto text-sm text-text-secondary">
      第 {{ roundCount }} / 10 轮
    </span>
  </div>
</template>
