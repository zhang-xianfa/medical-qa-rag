<script setup lang="ts">
import type { Message } from '@/types/message'
import { isReportContent } from '@/utils/report'
import { Stethoscope } from 'lucide-vue-next'
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
      'msg flex gap-2.5 animate-msg-in',
      isUser ? 'self-end flex-row-reverse max-w-[85%]' : 'self-start w-full max-w-full',
    ]"
  >
    <!-- Avatar -->
    <div
      :class="[
        'w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 self-end',
        isUser
          ? 'bg-gradient-to-br from-plum to-eggplant text-white text-xs font-medium'
          : 'bg-white border border-eggplant/8 shadow-soft',
      ]"
    >
      <template v-if="isUser">我</template>
      <Stethoscope v-else class="w-4 h-4 text-wisteria" :stroke-width="1.8" />
    </div>

    <!-- Bubble / Report -->
    <div
      :class="[
        isReport
          ? 'w-full min-w-0'
          : isUser
            ? 'px-4 py-2.5 rounded-2xl rounded-br-md bg-gradient-to-br from-[#7d5d96] to-[#5a3e6b] text-white/95 text-[15px] leading-7 shadow-soft'
            : 'px-4 py-2.5 rounded-2xl rounded-bl-md bg-white border border-eggplant/8 text-eggplant/85 text-[15px] leading-7 shadow-soft',
      ]"
    >
      <!-- 诊断报告 -->
      <DiagnosisReport v-if="isReport" :content="message.content" />
      <!-- 普通文本 -->
      <p v-else class="whitespace-pre-wrap break-words">{{ message.content }}</p>

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
