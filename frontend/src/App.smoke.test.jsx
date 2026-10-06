// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import App from './App.jsx'

// 这组用例同时充当两件事的验收：
//   1) P3 拆分后 App 与各 views/* 的 props 装配是否正确（装配错了渲染就会抛错或缺失内容）；
//   2) React.lazy 的代码分割是否真的能按需加载（切视图后能查到该视图独有文案）。

const originalFetch = global.fetch

function jsonResponse(body, { ok = true, status = 200 } = {}) {
  return { ok, status, text: async () => JSON.stringify(body) }
}

function mockHealthyBackend() {
  global.fetch = vi.fn((url) => {
    const target = String(url)
    // 注意顺序：更具体的路径必须排在 '/api/materials' 之前，否则会被泛匹配吃掉。
    if (target.includes('/api/health')) return Promise.resolve(jsonResponse({ status: 'ok' }))
    if (target.includes('/api/materials/import-capabilities')) {
      return Promise.resolve(jsonResponse({ ready: true, problems: [] }))
    }
    if (target.includes('/api/materials')) return Promise.resolve(jsonResponse([]))
    return Promise.resolve(jsonResponse({}))
  })
}

beforeEach(() => { mockHealthyBackend() })

afterEach(() => {
  cleanup()
  global.fetch = originalFetch
})

describe('App 冒烟', () => {
  it('渲染侧边栏五个导航项与首页标题', () => {
    render(<App />)
    for (const label of ['首页', '素材', '周测', '候选', '仪表盘']) {
      expect(screen.getByRole('button', { name: label })).toBeTruthy()
    }
    expect(screen.getByRole('heading', { name: '训练工作台' })).toBeTruthy()
  })

  it('健康检查通过且无素材时，展示就绪状态与空态引导', async () => {
    render(<App />)
    expect(await screen.findByText('训练核心已就绪')).toBeTruthy()
    expect(await screen.findByText('还没有开始训练')).toBeTruthy()
  })

  it('后端不可用时提示尚未启动', async () => {
    global.fetch = vi.fn(() => Promise.reject(new Error('offline')))
    render(<App />)
    expect(await screen.findByText('后端尚未启动')).toBeTruthy()
  })

  it('切换到素材视图时按需加载该视图', async () => {
    render(<App />)
    screen.getByRole('button', { name: '素材' }).click()
    expect(await screen.findByText('导入并进入训练')).toBeTruthy()
    expect(screen.getByRole('heading', { name: '素材' })).toBeTruthy()
  })

  it('切换到仪表盘视图时按需加载 P2 视图', async () => {
    render(<App />)
    screen.getByRole('button', { name: '仪表盘' }).click()
    expect(await screen.findByText('观察与解释层')).toBeTruthy()
  })

  it('切换到周测视图时按需加载周测视图', async () => {
    render(<App />)
    screen.getByRole('button', { name: '周测' }).click()
    expect(await screen.findByText('每周质量闸门')).toBeTruthy()
  })
})
