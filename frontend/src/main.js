import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import axios from 'axios'
import { clearAuth } from './auth.js'

axios.defaults.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Attach JWT token to every request
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('ng_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Redirect to /login on 401
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearAuth()
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

createApp(App).use(router).mount('#app')
