<script setup lang="ts">
import { useAuthStore } from '@/stores/authStore'
import AuthPage from '@/components/auth/AuthPage.vue'
import HomePage from '@/views/HomePage.vue'

const auth = useAuthStore()
</script>

<template>
  <AuthPage v-if="!auth.isAuthenticated" />
  <HomePage v-else />
</template>
