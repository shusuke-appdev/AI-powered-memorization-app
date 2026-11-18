import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode,process.cwd(),'VITE_');
  const key = env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
  if (key && !key.startsWith('sb_publishable_')) {
    throw new Error('VITE_SUPABASE_PUBLISHABLE_KEY must be a Supabase publishable key.');
  }
  return {
    plugins:[react()],
    server:process.env.STUDY_E2E === '1' ? {hmr:false} : {},
  };
});
