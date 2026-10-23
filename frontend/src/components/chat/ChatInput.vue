<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { ArrowUp, Plus } from 'lucide-vue-next'

const props = defineProps<{
  disabled: boolean
  placeholder: string
  done?: boolean
}>()

const emit = defineEmits<{
  send: [text: string]
  newSession: []
}>()

const text = ref('')
const boxRef = ref<HTMLTextAreaElement | null>(null)

function autoResize() {
  const el = boxRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 136) + 'px'
}

function onSend() {
  const t = text.value.trim()
  if (!t || props.disabled) return
  emit('send', t)
  text.value = ''
  nextTick(autoResize)
}

function onKeydown(e: KeyboardEvent) {
  // Enter 发送，Shift+Enter 换行
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    onSend()
  }
}
</script>

<template>
  <div class="w-full max-w-3xl px-4 pb-5 pt-1">
    <!-- 问诊结束：给一个明确的下一步，而不是让输入框一直灰着 -->
    <button
      v-if="done"
      class="w-full py-3 rounded-2xl bg-white border border-eggplant/10 text-sm text-plum font-medium shadow-soft hover:border-wisteria/50 hover:shadow-float transition-all flex items-center justify-center gap-2"
      @click="emit('newSession')"
    >
      <Plus class="w-4 h-4" />
      本次问诊已结束，开始新的问诊
    </button>

    <template v-else>
      <div
        :class="[
          'flex items-end gap-2 rounded-2xl bg-white border px-3 py-2 transition-all',
          disabled
            ? 'border-eggplant/6 bg-white/60'
            : 'border-eggplant/10 shadow-soft focus-within:border-wisteria/50 focus-within:shadow-float',
        ]"
      >
        <textarea
          ref="boxRef"
          v-model="text"
          rows="1"
          :placeholder="placeholder"
          :disabled="disabled"
          class="chat-textarea flex-1 bg-transparent px-1.5 py-2 text-[15px] leading-6 text-eggplant placeholder:text-eggplant/30 outline-none disabled:cursor-not-allowed font-sans"
          @input="autoResize"
          @keydown="onKeydown"
        />
        <button
          :disabled="disabled || !text.trim()"
          class="mb-0.5 w-9 h-9 flex items-center justify-center rounded-xl bg-gradient-to-br from-wisteria to-plum text-white transition-all hover:shadow-lg hover:shadow-wisteria/25 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:shadow-none"
          aria-label="发送"
          @click="onSend"
        >
          <ArrowUp class="w-4 h-4" :stroke-width="2.4" />
        </button>
      </div>
      <p class="mt-2 px-1 text-center text-[11px] text-eggplant/30">
        <span class="hidden sm:inline">Enter 发送 · Shift + Enter 换行 · </span>内容仅供健康参考
      </p>
    </template>
  </div>
</template>
