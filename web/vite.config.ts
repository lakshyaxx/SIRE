import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({plugins:[tailwindcss()],build:{assetsDir:'static'},server:{proxy:{'/api':'http://127.0.0.1:8000'}}});
