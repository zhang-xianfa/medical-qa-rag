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
  <div class="choices mt-3">
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
      <button
        v-for="(opt, i) in options.slice(0, 4)"
        :key="i"
        :disabled="disabled"
        class="choice-card group flex items-center gap-2.5 px-3 py-2.5 bg-white border border-lilac-light rounded-xl text-sm text-left text-eggplant/80 cursor-pointer hover:border-wisteria/60 hover:shadow-[0_4px_14px_rgba(139,107,158,0.14)] hover:-translate-y-px focus-visible:outline-2 focus-visible:outline-wisteria focus-visible:outline-offset-2 disabled:opacity-55 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
        @click="emit('select', opt.value, opt.label)"
      >
        <span class="choice-letter-bg inline-flex items-center justify-center w-5 h-5 rounded-md bg-wisteria-ghost text-wisteria text-[11px] font-semibold flex-shrink-0 transition-colors">
          {{ letters[i] }}
        </span>
        <span class="leading-snug">{{ opt.label }}</span>
      </button>
    </div>
    <p class="mt-2 text-[11px] text-eggplant/35">也可以在下方直接描述您的情况</p>
  </div>
</template>
