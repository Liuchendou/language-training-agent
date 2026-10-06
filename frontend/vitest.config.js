import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// 独立于 vite.config.js 存在，理由：vitest 一旦发现 vitest.config.js 就不再合并
// vite.config.js，因此这里必须自带 react 插件（组件测试需要 JSX 转换）。
//
// 默认 environment 取 node —— 待测的 readJson / detailOf / encodeWav 都是纯逻辑，
// 用不到 DOM，跑得更快。需要 DOM 的用例在文件顶部用
// `// @vitest-environment jsdom` 单独声明。
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    include: ['src/**/*.test.{js,jsx}'],
  },
})
