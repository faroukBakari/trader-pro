<script setup lang="ts">
/**
 * Global toast notification component wrapper.
 * Configures vue-sonner Toaster with unstyled mode and custom classes.
 * Styles are defined in @/assets/toast.css
 */
import { Toaster } from 'vue-sonner'

const toastClasses = {
  toast: 'toast-base',
  title: 'toast-title',
  description: 'toast-description',
  error: 'toast-error',
  warning: 'toast-warning',
  success: 'toast-success',
  info: 'toast-info',
}
</script>

<template>
  <Toaster
    position="bottom-center"
    :expand="false"
    :close-button="false"
    :unstyled="true"
    :toast-options="{ classes: toastClasses }"
  />
</template>
