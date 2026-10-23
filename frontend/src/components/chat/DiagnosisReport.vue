<script setup lang="ts">
import { computed, ref } from 'vue'
import DOMPurify from 'dompurify'
import { FileText, Copy, Check } from 'lucide-vue-next'
import { parseReport, detectRisk, RISK_LABEL } from '@/utils/report'

const props = defineProps<{
  content: string
}>()

const reportHtml = computed(() => DOMPurify.sanitize(parseReport(props.content)))
const risk = computed(() => detectRisk(props.content))

const copied = ref(false)
async function copyReport() {
  try {
    await navigator.clipboard.writeText(props.content)
    copied.value = true
    setTimeout(() => (copied.value = false), 1600)
  } catch {
    // 剪贴板不可用（非 HTTPS 场景常见）时静默失败
  }
}
</script>

<template>
  <div class="report-card rounded-2xl border border-eggplant/8 shadow-elevated overflow-hidden animate-report-in">
    <!-- 报告头 -->
    <div class="flex items-center gap-2 px-5 py-3.5 border-b border-eggplant/6 bg-white/60">
      <FileText class="w-4 h-4 text-blue-dark" :stroke-width="1.8" />
      <span class="text-sm font-semibold text-eggplant/85">AI 综合分析</span>
      <span v-if="risk" :class="['risk-badge', 'risk-' + risk]">{{ RISK_LABEL[risk] }}</span>

      <button
        class="ml-auto flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] text-eggplant/45 hover:text-wisteria hover:bg-wisteria-ghost transition-colors"
        @click="copyReport"
      >
        <Check v-if="copied" class="w-3.5 h-3.5" />
        <Copy v-else class="w-3.5 h-3.5" />
        {{ copied ? '已复制' : '复制' }}
      </button>
    </div>

    <!-- 报告正文 -->
    <div class="px-5 py-4" v-html="reportHtml" />
  </div>
</template>
