import {defineConfig} from '@playwright/test';

const port = Number(process.env.STUDY_TEST_PORT ?? 4170);
const url = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir:'./browser',
  workers:1,
  use:{
    baseURL:url,
    launchOptions:process.env.STUDY_CHROMIUM_PATH ? {executablePath:process.env.STUDY_CHROMIUM_PATH} : {},
  },
  projects:[
    {name:'mobile',use:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}},
    {name:'small-dark',use:{viewport:{width:360,height:760},isMobile:true,hasTouch:true,colorScheme:'dark'}},
    {name:'desktop',use:{viewport:{width:1280,height:900}}},
  ],
  webServer:{
    command:`node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port} --strictPort`,
    url,
    reuseExistingServer:process.env.STUDY_REUSE_TEST_SERVER === '1',
    env:{STUDY_E2E:'1',VITE_SUPABASE_URL:'https://example.supabase.co',VITE_SUPABASE_PUBLISHABLE_KEY:'sb_publishable_test_fixture_only'},
  },
});
