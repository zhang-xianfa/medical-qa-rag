<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  disabled: boolean
  placeholder: string
}>()

const emit = defineEmits<{
  send: [text: string]
}>()

const text = ref('')

function onSend() {
  const t = text.value.trim()
  if (!t) return
  emit('send', t)
  text.value = ''
}
</script>

<template>
  <div class="chat-input w-full max-w-3xl px-4 pb-4 flex gap-2.5">
    <input
      v-model="text"
      type="text"
      :placeholder="placeholder"
      :disabled="disabled"
      class="flex-1 px-3.5 py-2.5 border-1.5 border-lilac-light rounded-md text-sm outline-none transition-colors focus:border-wisteria disabled:bg-lavender bg-white font-sans"
      @keydown.enter="onSend"
    />
    <button
      :disabled="disabled || !text.trim()"
      class="px-6 py-2.5 bg-wisteria text-white rounded-md text-sm font-medium cursor-pointer transition-colors hover:bg-eggplant disabled:opacity-60 disabled:cursor-not-allowed whitespace-nowrap font-sans"
      @click="onSend"
    >
      发送
    </button>
  </div>
</template>
