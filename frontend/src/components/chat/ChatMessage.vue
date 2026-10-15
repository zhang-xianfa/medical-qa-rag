<script setup lang="ts">
import type { Message } from '@/types/message'
import { isReportContent } from '@/utils/report'
import ChoiceCards from './ChoiceCards.vue'
import DiagnosisReport from './DiagnosisReport.vue'

const props = defineProps<{
  message: Message
  disabledChoices: boolean
}>()

const emit = defineEmits<{
  selectChoice: [value: string, label: string]
}>()

const isUser = props.message.role === 'user'
const isReport = props.message.role === 'assistant' && isReportContent(props.message.content, props.message.options)
</script>

<template>
  <div
    :class="[
      'msg flex gap-2 max-w-[82%] animate-msg-in',
      isUser ? 'self-end flex-row-reverse' : 'self-start',
    ]"
  >
    <!-- Avatar -->
    <div
      :class="[
        'avatar-icon w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 self-end',
        isUser ? 'bg-eggplant text-white' : 'bg-wisteria-ghost',
      ]"
    >
      {{ isUser ? '我' : 'AI' }}
    </div>

    <!-- Bubble -->
    <div
      :class="[
        'bubble rounded-md px-3.5 py-2.5 text-sm leading-relaxed shadow-card',
        isUser ? 'bg-eggplant text-white/90' : 'bg-white',
      ]"
    >
      <!-- 诊断报告 -->
      <DiagnosisReport v-if="isReport" :content="message.content" />
      <!-- 普通文本 -->
      <p v-else class="whitespace-pre-wrap">{{ message.content }}</p>

      <!-- 选择题选项 -->
      <ChoiceCards
        v-if="message.options && message.options.length > 0"
        :options="message.options"
        :disabled="disabledChoices"
        @select="(value, label) => emit('selectChoice', value, label)"
      />
    </div>
  </div>
</template>
