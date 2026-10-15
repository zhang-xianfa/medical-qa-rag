<script setup lang="ts">
import type { OptionCard } from '@/types/message'

defineProps<{
  options: OptionCard[]
  disabled: boolean
}>()

const emit = defineEmits<{
  select: [value: string, label: string]
}>()

const letters = 'ABCDEFGH'
</script>

<template>
  <div class="choices flex flex-wrap items-center gap-2 mt-2">
    <button
      v-for="(opt, i) in options.slice(0, 4)"
      :key="i"
      :disabled="disabled"
      class="choice-card inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border-1.5 border-lilac-light rounded-md text-sm cursor-pointer hover:border-wisteria hover:shadow-[0_2px_8px_rgba(139,107,158,0.15)] hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-wisteria focus-visible:outline-offset-2 disabled:opacity-60 disabled:cursor-not-allowed"
      @click="emit('select', opt.value, opt.label)"
    >
      <span class="choice-letter-bg inline-flex items-center justify-center w-5 h-5 rounded-full bg-wisteria-ghost text-wisteria text-xs font-semibold flex-shrink-0">
        {{ letters[i] }}
      </span>
      {{ opt.label }}
    </button>
    <p class="choice-hint w-full mt-1 text-xs text-lilac">也可以直接在下方输入框描述您的情况</p>
  </div>
</template>
