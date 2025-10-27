import './assets/main.css'

import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import router from './router'

// Make touch and wheel events passive by default to improve scrolling performance
// This addresses Chrome's "Added non-passive event listener" warnings from third-party libraries
// if (typeof EventTarget !== 'undefined') {
//   const originalAddEventListener = EventTarget.prototype.addEventListener
//   EventTarget.prototype.addEventListener = function (
//     type: string,
//     listener: EventListenerOrEventListenerObject | null,
//     options?: boolean | AddEventListenerOptions
//   ) {
//     if (type === 'touchstart' || type === 'touchmove' || type === 'wheel' || type === 'mousewheel') {
//       if (typeof options === 'object' && options !== null) {
//         options.passive = options.passive !== false
//       } else if (typeof options === 'boolean' || options === undefined) {
//         options = { passive: true, capture: typeof options === 'boolean' ? options : false }
//       }
//     }
//     return originalAddEventListener.call(this, type, listener, options)
//   }
// }

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
