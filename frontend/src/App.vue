<template>
  <v-app>
    <v-app-bar color="primary" density="comfortable">
      <v-app-bar-title>Biometric Operations</v-app-bar-title>
      <v-chip class="mr-4" color="white" variant="tonal">Operations console</v-chip>
    </v-app-bar>
    <v-main>
      <Dashboard />
    </v-main>
  </v-app>
</template>

<script setup>
import Dashboard from './components/Dashboard.vue'
</script>
