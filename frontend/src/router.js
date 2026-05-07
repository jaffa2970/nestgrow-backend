import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import Registration from './views/Registration.vue'

const routes = [
  { path: '/login', component: Login },
  { path: '/register', component: Registration },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (to.path === '/login' || to.path === '/register') {
    return
  }

  const token = localStorage.getItem('ng_token')
  if (!token) {
    return '/login'
  }

  // Check license registration
  try {
    const { data } = await axios.get('/license/')
    if (!data.registrato) {
      return '/register'
    }
  } catch {
    // If license check fails (e.g. 401), redirect to login
    return '/login'
  }
})

export default router
