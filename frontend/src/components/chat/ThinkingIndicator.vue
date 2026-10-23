<script setup lang="ts">
import { Stethoscope } from 'lucide-vue-next'
</script>

<template>
  <div class="flex gap-2.5 self-start animate-msg-in">
    <div class="w-8 h-8 rounded-full bg-white border border-eggplant/8 shadow-soft flex items-center justify-center flex-shrink-0 self-end">
      <Stethoscope class="w-4 h-4 text-wisteria" :stroke-width="1.8" />
    </div>
    <div class="px-4 py-3 rounded-2xl rounded-bl-md bg-white border border-eggplant/8 shadow-soft flex items-center gap-2">
      <span class="flex gap-1">
        <span class="w-1.5 h-1.5 rounded-full bg-wisteria/40 animate-bounce [animation-delay:-0.3s]" />
        <span class="w-1.5 h-1.5 rounded-full bg-wisteria/60 animate-bounce [animation-delay:-0.15s]" />
        <span class="w-1.5 h-1.5 rounded-full bg-wisteria/80 animate-bounce" />
      </span>
      <span class="text-xs text-eggplant/45">正在分析您的情况</span>
    </div>
  </div>
</template>
