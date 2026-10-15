<script setup lang="ts">
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { parseReport } from '@/utils/report'

const props = defineProps<{
  content: string
}>()

const reportHtml = computed(() => DOMPurify.sanitize(parseReport(props.content)))
</script>

<template>
  <div class="report-card bg-white rounded-lg p-5 shadow-elevated border-l-4 border-blue animate-report-in">
    <div v-html="reportHtml" />
  </div>
</template>
