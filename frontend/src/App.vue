<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div id="app-container">
    <header>
      <div class="header-content">
        <router-link to="/" class="logo">
          <!-- <h1>TraderPRO Backend</h1> -->
        </router-link>
        <!-- <p>Monitor your TraderPRO backend status</p> -->
      </div>
    </header>

    <main>
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
#app-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 20px;
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
