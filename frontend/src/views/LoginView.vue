<script setup lang="ts">
import { useAuthStore } from '@/stores/authStore'
import { storeToRefs } from 'pinia'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { GoogleSignInButton, type CredentialResponse } from 'vue3-google-signin'

const authStore = useAuthStore()
const { isAuthenticated, isLoading, error } = storeToRefs(authStore)
const router = useRouter()
const showGoogleButton = ref(true)

onMounted(() => {
  if (isAuthenticated.value) {
    const redirectPath = router.currentRoute.value.query.redirect as string
    router.push(redirectPath || '/chart')
  }
})

async function handleGoogleSignIn(response: CredentialResponse) {
  console.log('Google Sign-In response received:', { hasCredential: !!response.credential })
  showGoogleButton.value = false
  isLoading.value = true
  error.value = null

  try {
    await authStore.loginWithGoogleToken(response.credential!)

    if (isAuthenticated.value) {
      const redirectPath = router.currentRoute.value.query.redirect as string
      router.push(redirectPath || '/chart')
    }
  } catch (err) {
    console.error('Login failed:', err)
    const errorMessage = err instanceof Error ? err.message : 'Login failed'
    error.value = errorMessage.includes('401')
      ? 'Invalid Google token. Please try again.'
      : errorMessage.includes('500')
        ? 'Server error. Please try again later.'
        : errorMessage
    showGoogleButton.value = true
  } finally {
    isLoading.value = false
  }
}

function handleGoogleError() {
  console.error('Google Sign-In button error')
  error.value = 'Google sign-in failed. Please check your connection and try again.'
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>Trader Pro</h1>
        <p>Sign in to access your trading platform</p>
      </div>

      <div class="login-content">
        <div v-if="error" class="error-message" role="alert">
          {{ error }}
        </div>

        <div class="login-button-container">
          <GoogleSignInButton
            v-if="showGoogleButton && !isLoading"
            type="standard"
            theme="outline"
            size="large"
            text="signin_with"
            shape="rectangular"
            logo_alignment="left"
            width="350"
            @success="handleGoogleSignIn"
            @error="handleGoogleError"
          />

          <div v-if="isLoading" class="loading-state">
            <div class="spinner" aria-label="Loading"></div>
            <p>Signing in...</p>
          </div>
        </div>
      </div>

      <div class="login-footer">
        <p class="disclaimer">
          By signing in, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 1rem;
}

.login-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  max-width: 420px;
  width: 100%;
  padding: 2.5rem;
}

.login-header {
  text-align: center;
  margin-bottom: 2rem;
}

.login-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #1a202c;
  margin: 0 0 0.5rem 0;
}

.login-header p {
  font-size: 1rem;
  color: #718096;
  margin: 0;
}

.login-content {
  margin-bottom: 1.5rem;
}

.error-message {
  background: #fed7d7;
  border: 1px solid #fc8181;
  border-radius: 6px;
  color: #c53030;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.login-button-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.google-signin-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.75rem 1.5rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 500;
  color: #4a5568;
  cursor: pointer;
  transition: all 0.2s;
}

.google-signin-button:hover:not(:disabled) {
  background: #f7fafc;
  border-color: #cbd5e0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.google-signin-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.google-icon {
  width: 20px;
  height: 20px;
}

.loading-state {
  text-align: center;
  padding: 1rem;
}

.spinner {
  border: 3px solid #e2e8f0;
  border-top: 3px solid #667eea;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.loading-state p {
  color: #718096;
  font-size: 0.875rem;
  margin: 0;
}

.login-footer {
  text-align: center;
  padding-top: 1.5rem;
  border-top: 1px solid #e2e8f0;
}

.disclaimer {
  font-size: 0.75rem;
  color: #a0aec0;
  margin: 0;
  line-height: 1.5;
}
</style>
