import { createRouter, createWebHistory } from 'vue-router';
import type { RouteLocationNormalized, NavigationGuardNext } from 'vue-router';
import MainRoutes from './MainRoutes';
import AuthRoutes from './AuthRoutes';
import { useAuthStore } from '@/stores/auth';
import { useUIStore } from '@/stores/ui';

// Proper module augmentation for route meta
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

// Combined navigation guard with proper types
router.beforeEach(async (
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext
) => {
  const authStore = useAuthStore();
  const uiStore = useUIStore();
  
  // Set loading state
  uiStore.isLoading = true;
  
  // Initialize auth store if not already initialized
  if (!authStore.initialized) {
    try {
      await authStore.init();
    } catch (error) {
      console.error('Auth store initialization failed:', error);
    }
  }

  // Debug logging
  console.log('Navigation guard:', {
    to: to.path,
    authenticated: authStore.isAuthenticated,
    requiresAuth: to.meta?.requiresAuth
  });

  // Check if route requires authentication
  if (to.meta?.requiresAuth && !authStore.isAuthenticated) {
    uiStore.isLoading = false; // Reset loading state
    next('/auth/login');
    return;
  }
  
  // Redirect authenticated users away from auth pages
  if (to.path.startsWith('/auth') && authStore.isAuthenticated) {
    uiStore.isLoading = false; // Reset loading state
    next('/dashboard');
    return;
  }

  next();
});

router.afterEach(() => {
  const uiStore = useUIStore();
  uiStore.isLoading = false;
});

export { router };
export default router;