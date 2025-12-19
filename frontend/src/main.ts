import './assets/main.css'
import './assets/toast.css'

import { createApp } from 'vue'
import GoogleSignInPlugin from 'vue3-google-signin'

import { errorService } from '@/errors'
import App from './App.vue'
import router from './router'


const app = createApp(App)

app.use(router)
app.use(GoogleSignInPlugin, {
  clientId: import.meta.env.VITE_GOOGLE_CLIENT_ID,
})

// Global Vue error handler - catches errors in component lifecycle, watchers, etc.
app.config.errorHandler = (err) => {
  errorService.handle(err)
}

// Global window error handler - catches uncaught errors
window.onerror = (_message, _source, _lineno, _colno, error) => {
  errorService.handle(error)
  return false // Allow default console logging
}

// Global unhandled promise rejection handler
window.onunhandledrejection = (event) => {
  errorService.handle(event.reason)
}

app.mount('#app')

