<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <header>
    <div class="header-content">
      <router-link to="/" class="logo">
        <h1>Trading API Frontend</h1>
      </router-link>
      <p>Monitor your FastAPI backend status</p>
    </div>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style scoped>
header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 2rem 0;
  text-align: center;
  margin-bottom: 2rem;
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
  min-height: calc(100vh - 200px);
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
