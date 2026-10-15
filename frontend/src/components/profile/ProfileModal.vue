<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAuthStore } from '@/stores/authStore'

const props = defineProps<{
  show: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const auth = useAuthStore()

// Form fields
const nickname = ref('')
const gender = ref('')
const height = ref<number | undefined>()
const weight = ref<number | undefined>()
const bloodType = ref('')
const allergies = ref('')
const chronic = ref('')

const saving = ref(false)

watch(() => props.show, async (val) => {
  if (val && auth.user) {
    const u = auth.user
    nickname.value = u.nickname || ''
    gender.value = u.gender || ''
    height.value = u.height
    weight.value = u.weight
    bloodType.value = u.blood_type || ''
    allergies.value = (u.medical_info?.allergies || []).join('，')
    chronic.value = (u.medical_info?.chronic_diseases || []).join('，')
  }
})

async function onSave() {
  saving.value = true
  try {
    const data: Record<string, unknown> = {}
    if (nickname.value) data.nickname = nickname.value
    if (gender.value) data.gender = gender.value
    if (height.value) data.height = height.value
    if (weight.value) data.weight = weight.value
    if (bloodType.value) data.blood_type = bloodType.value
    if (allergies.value) data.allergies = allergies.value.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean)
    if (chronic.value) data.chronic_diseases = chronic.value.split(/[,，]/).map((s: string) => s.trim()).filter(Boolean)

    await auth.updateProfile(data)
    emit('close')
  } catch (e) {
    console.error('updateProfile:', e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="fixed inset-0 z-40 bg-black/30 flex items-center justify-center"
      @click.self="emit('close')"
    >
      <div class="bg-white rounded-lg p-8 w-[min(32rem,90vw)] max-h-[85vh] overflow-y-auto shadow-elevated">
        <h2 class="font-brand text-lg mb-5">个人信息</h2>

        <div class="mb-3">
          <label class="block text-xs text-text-secondary mb-1">昵称</label>
          <input v-model="nickname" maxlength="50" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans" />
        </div>

        <div class="flex gap-2.5 mb-3">
          <div class="flex-1">
            <label class="block text-xs text-text-secondary mb-1">性别</label>
            <select v-model="gender" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans">
              <option value="">未设置</option>
              <option value="男">男</option>
              <option value="女">女</option>
            </select>
          </div>
          <div class="flex-1">
            <label class="block text-xs text-text-secondary mb-1">血型</label>
            <select v-model="bloodType" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans">
              <option value="">未设置</option>
              <option>A</option>
              <option>B</option>
              <option>AB</option>
              <option>O</option>
            </select>
          </div>
        </div>

        <div class="flex gap-2.5 mb-3">
          <div class="flex-1">
            <label class="block text-xs text-text-secondary mb-1">身高 (cm)</label>
            <input v-model.number="height" type="number" placeholder="170" min="50" max="250" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans" />
          </div>
          <div class="flex-1">
            <label class="block text-xs text-text-secondary mb-1">体重 (kg)</label>
            <input v-model.number="weight" type="number" placeholder="65" min="20" max="300" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans" />
          </div>
        </div>

        <div class="mb-3">
          <label class="block text-xs text-text-secondary mb-1">过敏史（逗号分隔）</label>
          <input v-model="allergies" placeholder="青霉素, 花粉" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans" />
        </div>

        <div class="mb-5">
          <label class="block text-xs text-text-secondary mb-1">慢性病史</label>
          <input v-model="chronic" placeholder="高血压, 糖尿病" class="w-full px-2.5 py-2 border-1.5 border-lilac-light rounded-sm text-sm outline-none focus:border-wisteria font-sans" />
        </div>

        <div class="flex gap-2.5">
          <button class="flex-1 py-2 bg-lavender border border-lilac-light rounded-sm text-sm cursor-pointer hover:bg-lilac-light transition-colors font-sans" @click="emit('close')">取消</button>
          <button :disabled="saving" class="flex-1 py-2 bg-wisteria text-white rounded-sm text-sm cursor-pointer hover:bg-plum transition-colors disabled:opacity-60 font-sans" @click="onSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
