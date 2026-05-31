import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import Login from './views/Login.vue'
import Dashboard from './views/Dashboard.vue'
import Registration from './views/Registration.vue'
import Utenti from './views/Utenti.vue'
import { ruolo } from './auth.js'

const routes = [
  { path: '/login', component: Login },
  { path: '/register', component: Registration },
  {
    path: '/',
    component: Dashboard,
    meta: { requiresAuth: true },
  },
  {
    path: '/utenti',
    component: Utenti,
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  if (to.path === '/login' || to.path === '/register') return

  const token = localStorage.getItem('ng_token')
  if (!token) return '/login'

  if (to.meta.requiresAdmin && ruolo.value !== 'administrator') {
    return '/'
  }

  try {
    const { data } = await axios.get('/license/')
    if (!data.registrato) return '/register'
  } catch {
    return '/login'
  }
})

export default router
