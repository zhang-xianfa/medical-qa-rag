import { ref, nextTick, type Ref } from 'vue'

/** 自动滚动到底部，尊重用户手动上滚 */
export function useScroll(containerRef: Ref<HTMLElement | null>) {
  const isNearBottom = ref(true)

  function onScroll() {
    const el = containerRef.value
    if (!el) return
    // 距离底部 < 80px 视为"在底部"
    isNearBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  async function scrollToBottom() {
    await nextTick()
    const el = containerRef.value
    if (el && isNearBottom.value) {
      el.scrollTop = el.scrollHeight
    }
  }

  return { onScroll, scrollToBottom, isNearBottom }
}
