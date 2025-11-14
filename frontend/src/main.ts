import './assets/main.css'

import { createApp } from 'vue'
import GoogleSignInPlugin from 'vue3-google-signin'

import App from './App.vue'
import router from './router'


const app = createApp(App)

app.use(router)
app.use(GoogleSignInPlugin, {
  clientId: import.meta.env.VITE_GOOGLE_CLIENT_ID,
})

app.mount('#app')

