import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import { router } from './router';
import vuetify from './plugins/vuetify';
import '@/scss/style.scss';
import { PerfectScrollbarPlugin } from 'vue3-perfect-scrollbar';
import VueTablerIcons from 'vue-tabler-icons';
import VueApexCharts from 'vue3-apexcharts';
import Antd from 'ant-design-vue';
import 'ant-design-vue/dist/reset.css';
import { useAuthStore } from '@/stores/auth';

// google-fonts
import '@fontsource/public-sans/400.css';
import '@fontsource/public-sans/500.css';
import '@fontsource/public-sans/600.css';
import '@fontsource/public-sans/700.css';

//Mock Api data
import { fakeBackend } from '@/utils/helpers/fake-backend';

//i18n
import { createI18n } from 'vue-i18n';
import messages from '@/utils/locales/messages';

const i18n = createI18n({
  locale: 'en',
  messages: messages,
  silentTranslationWarn: true,
  silentFallbackWarn: true
});

async function initApp() {
  // 1. Create app and pinia first
  const app = createApp(App);
  const pinia = createPinia();
  
  app.use(pinia); // Pinia must be registered BEFORE any store access
  
  // 2. Initialize auth store BEFORE router
  const authStore = useAuthStore();
  await authStore.init(); // Wait for auth state to hydrate
  
  // 3. Mock backend and other plugins
  fakeBackend();
  
  // 4. Register router and other plugins
  app.use(router);
  app.use(PerfectScrollbarPlugin);
  app.use(VueTablerIcons);
  app.use(Antd);
  app.use(i18n);
  app.use(VueApexCharts);
  app.use(vuetify);

  // 5. Mount the app
  app.mount('#app');
}

initApp().catch((error) => {
  console.error('Application initialization failed:', error);
});