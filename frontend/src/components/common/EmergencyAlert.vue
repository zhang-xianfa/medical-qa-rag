<script setup lang="ts">
defineProps<{
  show: boolean
  redFlags: string[]
  guidance: string
}>()

const emit = defineEmits<{
  close: []
}>()
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
    >
      <div class="bg-white rounded-lg p-6 max-w-md w-[90vw] shadow-elevated animate-report-in">
        <div class="flex items-center gap-3 mb-4">
          <div class="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-lg font-bold">
            !
          </div>
          <div>
            <h2 class="text-lg font-semibold text-red-600">紧急情况</h2>
            <p class="text-xs text-text-secondary">请立即采取行动</p>
          </div>
        </div>

        <div class="bg-red-50 rounded-md p-4 mb-4">
          <p class="text-sm text-red-800 leading-relaxed whitespace-pre-wrap">{{ guidance }}</p>
        </div>

        <div v-if="redFlags.length > 0" class="mb-4">
          <p class="text-xs text-text-secondary mb-2">检测到的红旗症状：</p>
          <div class="flex flex-wrap gap-1.5">
            <span
              v-for="rf in redFlags"
              :key="rf"
              class="px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs"
            >
              {{ rf }}
            </span>
          </div>
        </div>

        <p class="text-xs text-mauve mb-4">
          ⚕ 本系统为AI辅助工具，此急救指引为自动触发。请立即拨打120寻求专业急救。
        </p>

        <button
          class="w-full py-2.5 bg-red-600 text-white rounded-md font-medium hover:bg-red-700 transition-colors"
          @click="emit('close')"
        >
          我知道了
        </button>
      </div>
    </div>
  </Teleport>
</template>
