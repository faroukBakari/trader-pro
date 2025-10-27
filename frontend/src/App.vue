<script setup lang="ts">
import { RouterView } from 'vue-router'
import ApiStatus from '@/components/ApiStatus.vue'
</script>

<template>
  <div id="app-container">
    <main>
      <RouterView />
    </main>

    <footer>
      <ApiStatus />
    </footer>
  </div>
</template>

<style scoped>
#app-container {
  max-width: 1600px;
  margin: 0 auto;
  padding: 0 20px;
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
}

footer {
  margin-top: 1rem;
  padding: 0.5rem 0;
  border-top: 1px solid #e0e0e0;
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
