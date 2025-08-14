import { createRouter, createWebHistory } from 'vue-router';
import MainRoutes from './MainRoutes';
import AuthRoutes from './AuthRoutes';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';

// Define types inline since vue-router exports might not be available
interface RouteLocation {
  path: string;
  meta?: { requiresAuth?: boolean };
  [key: string]: any;
}

interface NavigationGuard {
  (path?: string): void;
  (): void;
}

// Proper module augmentation
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean;
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/:pathMatch(.*)*',
      component: () => import('@/views/pages/maintenance/error/Error404Page.vue')
    },
    MainRoutes,
    AuthRoutes
  ]
});

router.beforeEach(async (
  to: RouteLocation, 
  from: RouteLocation, 
  next: NavigationGuard
) => {
  const authStore = useAuthStore();
  
  if (!authStore.initialized) {
    await authStore.init();
  }

  if (to.meta?.requiresAuth && !authStore.isAuthenticated) {
    next('/auth/login');
    return;
  }
  
  if (to.path.startsWith('/auth') && authStore.isAuthenticated) {
    next('/dashboard');
    return;
  }

  next();
});

router.beforeEach((
  to: RouteLocation, 
  from: RouteLocation, 
  next: NavigationGuard
) => {
  const uiStore = useUIStore();
  uiStore.isLoading = true;
  next();
});

router.afterEach(() => {
  const uiStore = useUIStore();
  uiStore.isLoading = false;
});

export { router };
export default router;