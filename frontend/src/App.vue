<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppToaster from '@/components/AppToaster.vue'
import ApiStatus from '@/components/ApiStatus.vue'
</script>

<template>
  <div id="app-container">
    <AppToaster />

    <main>
      <RouterView />
    </main>

    <ApiStatus />
  </div>
</template>

<style scoped>
#app-container {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 2rem 0;
  text-align: center;
  margin: 0 -20px 2rem -20px;
}

.logo {
  text-decoration: none;
  color: inherit;
}

.logo:hover {
  opacity: 0.9;
}

.header-content h1 {
  margin: 0;
  font-size: 2.5rem;
  font-weight: 600;
  transition: opacity 0.2s ease;
}

.header-content p {
  margin: 0.5rem 0 0 0;
  font-size: 1.1rem;
  opacity: 0.9;
}

main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

@media (max-width: 768px) {
  .header-content h1 {
    font-size: 2rem;
  }

  .header-content p {
    font-size: 1rem;
  }
}
</style>
