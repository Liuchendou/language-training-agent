import { describe, it, expect } from 'vitest'
import { readJson, detailOf } from './api.js'

// readJson / detailOf 是纯逻辑，只依赖 response 的 ok / status / text 三个成员，
// 因此不必起 jsdom，直接用最小替身。
function fakeResponse({ ok = true, status = 200, body = '', throwOnRead = false } = {}) {
  return {
    ok,
    status,
    text: async () => {
      if (throwOnRead) throw new Error('connection reset')
      return body
    },
  }
}

describe('readJson', () => {
  it('正常 JSON 对象原样解析', async () => {
    expect(await readJson(fakeResponse({ body: '{"status":"ok"}' }))).toEqual({ status: 'ok' })
  })

  it('JSON 数组原样解析', async () => {
    expect(await readJson(fakeResponse({ body: '[{"material_id":"m1"}]' })))
      .toEqual([{ material_id: 'm1' }])
  })

  it('读取响应本身失败时给出连接中断提示', async () => {
    await expect(readJson(fakeResponse({ throwOnRead: true })))
      .rejects.toThrow('读取服务响应失败：连接被中断，请确认后端仍在运行。')
  })

  it('空响应体且 ok 时提示服务返回空响应', async () => {
    await expect(readJson(fakeResponse({ body: '   ' })))
      .rejects.toThrow('服务返回了空响应，请确认后端仍在运行后重试。')
  })

  it('空响应体且非 ok 时带出 HTTP 状态码', async () => {
    await expect(readJson(fakeResponse({ ok: false, status: 502, body: '' })))
      .rejects.toThrow('请求失败（HTTP 502）')
  })

  it('非 JSON 响应体时提示查看后端日志', async () => {
    await expect(readJson(fakeResponse({ ok: false, status: 500, body: '<html>oops</html>' })))
      .rejects.toThrow('服务返回了非 JSON 响应（HTTP 500）')
  })
})

describe('detailOf', () => {
  it('detail 为字符串时直接返回', () => {
    expect(detailOf({ detail: '素材不存在' }, '兜底')).toBe('素材不存在')
  })

  it('detail 为对象时取其中的 message', () => {
    expect(detailOf({ detail: { message: '状态不允许' } }, '兜底')).toBe('状态不允许')
  })

  it('detail 缺失时返回兜底文案', () => {
    expect(detailOf({}, '兜底')).toBe('兜底')
  })

  it('payload 为 null 时返回兜底文案', () => {
    expect(detailOf(null, '兜底')).toBe('兜底')
  })

  it('detail 为纯空白字符串时返回兜底文案', () => {
    expect(detailOf({ detail: '   ' }, '兜底')).toBe('兜底')
  })

  it('detail.message 不是字符串时返回兜底文案', () => {
    expect(detailOf({ detail: { message: 42 } }, '兜底')).toBe('兜底')
  })
})
