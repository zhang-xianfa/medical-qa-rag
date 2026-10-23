<script setup lang="ts">
import { computed } from 'vue'
import { Menu, Check } from 'lucide-vue-next'
import { useMessageStore } from '@/stores/messageStore'

const emit = defineEmits<{ toggleMenu: [] }>()

const msgStore = useMessageStore()
const MAX_ROUNDS = 10

const stage = computed(() => {
  if (msgStore.isDiagnosisDone) return 2
  if (msgStore.messages.length > 0) return 1
  return 0
})

const stages = ['信息采集', '专科分析', '诊断报告']

const roundCount = computed(() => {
  const last = msgStore.messages.filter(m => m.round_number > 0).pop()
  return Math.min(last?.round_number ?? 0, MAX_ROUNDS)
})

const progress = computed(() => Math.round((roundCount.value / MAX_ROUNDS) * 100))
</script>

<template>
  <header class="w-full max-w-3xl px-4 pt-4 pb-2 flex items-center gap-3">
    <!-- 移动端菜单 -->
    <button
      class="md:hidden p-2 -ml-1 rounded-lg text-eggplant/70 hover:bg-white hover:shadow-soft transition-all"
      aria-label="打开侧边栏"
      @click="emit('toggleMenu')"
    >
      <Menu class="w-5 h-5" />
    </button>

    <!-- 阶段指示器 -->
    <div class="hidden sm:flex items-center gap-1.5">
      <template v-for="(label, i) in stages" :key="label">
        <div
          :class="[
            'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-colors',
            i < stage ? 'text-wisteria/70' : '',
            i === stage ? 'bg-white text-plum font-medium shadow-soft' : 'text-eggplant/40',
          ]"
        >
          <span
            :class="[
              'w-4 h-4 rounded-full flex items-center justify-center text-[10px]',
              i < stage ? 'bg-wisteria/15 text-wisteria' : '',
              i === stage ? 'bg-wisteria text-white' : 'bg-eggplant/10',
            ]"
          >
            <Check v-if="i < stage" class="w-2.5 h-2.5" :stroke-width="3" />
            <template v-else>{{ i + 1 }}</template>
          </span>
          {{ label }}
        </div>
        <span v-if="i < stages.length - 1" class="w-3 h-px bg-eggplant/10" />
      </template>
    </div>

    <!-- 轮次进度 -->
    <div v-if="msgStore.messages.length > 0" class="ml-auto flex items-center gap-2.5">
      <span class="text-[11px] text-eggplant/45 whitespace-nowrap tabular-nums">
        第 {{ roundCount }} / {{ MAX_ROUNDS }} 轮
      </span>
      <div class="hidden sm:block w-16 h-1.5 rounded-full bg-eggplant/10 overflow-hidden">
        <div
          class="h-full rounded-full bg-gradient-to-r from-wisteria to-blue transition-all duration-500"
          :style="{ width: progress + '%' }"
        />
      </div>
    </div>
  </header>
</template>
