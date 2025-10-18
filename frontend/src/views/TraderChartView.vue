<template>
  <main>
    <TraderChartContainer :enableTrading="true" />
  </main>
</template>

<script setup lang="ts">
import TraderChartContainer from '@/components/TraderChartContainer.vue'
</script>

<style scoped>
main {
  padding: 0;
}
</style>
