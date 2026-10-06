import { describe, it, expect } from 'vitest'
import { encodeWav } from './wavRecorder.js'

// encodeWav 只用 ArrayBuffer / DataView / Blob，不碰 DOM，所以跑默认的 node 环境即可。
// 这段编码一旦写错，后端朗读评分会静默拿到损坏音频，界面上完全看不出来——正是最需要回归防护的地方。
async function viewOf(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer())
  return { bytes, view: new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength) }
}

function ascii(bytes, start, length) {
  return String.fromCharCode(...bytes.slice(start, start + length))
}

describe('encodeWav', () => {
  it('无采样时产出 44 字节的 WAV 头', async () => {
    const { bytes } = await viewOf(encodeWav([], 16000))
    expect(bytes.length).toBe(44)
  })

  it('声明 MIME 类型为 audio/wav', () => {
    expect(encodeWav([], 16000).type).toBe('audio/wav')
  })

  it('写入 RIFF / WAVE / fmt / data 四个标记', async () => {
    const { bytes } = await viewOf(encodeWav([], 16000))
    expect(ascii(bytes, 0, 4)).toBe('RIFF')
    expect(ascii(bytes, 8, 4)).toBe('WAVE')
    expect(ascii(bytes, 12, 4)).toBe('fmt ')
    expect(ascii(bytes, 36, 4)).toBe('data')
  })

  it('头部按 16 位单声道 PCM 填写', async () => {
    const { view } = await viewOf(encodeWav([], 16000))
    expect(view.getUint32(16, true)).toBe(16)     // fmt 块长度
    expect(view.getUint16(20, true)).toBe(1)      // 编码格式 PCM
    expect(view.getUint16(22, true)).toBe(1)      // 声道数 mono
    expect(view.getUint32(24, true)).toBe(16000)  // 采样率
    expect(view.getUint32(28, true)).toBe(32000)  // 字节率 = 采样率 × 2
    expect(view.getUint16(32, true)).toBe(2)      // 块对齐
    expect(view.getUint16(34, true)).toBe(16)     // 位深
  })

  it('长度字段随采样数增长，且覆盖全部 chunk', async () => {
    const { bytes, view } = await viewOf(encodeWav([new Float32Array([0, 0.5, -0.5]), new Float32Array([1, -1])], 8000))
    expect(bytes.length).toBe(44 + 5 * 2)
    expect(view.getUint32(4, true)).toBe(36 + 5 * 2)  // RIFF 块长度
    expect(view.getUint32(40, true)).toBe(5 * 2)      // data 块长度
  })

  it('采样值超出 [-1, 1] 时钳制到 16 位边界，不产生溢出', async () => {
    const { view } = await viewOf(encodeWav([new Float32Array([2, -2])], 8000))
    expect(view.getInt16(44, true)).toBe(32767)   // 0x7fff 上限
    expect(view.getInt16(46, true)).toBe(-32768)  // -0x8000 下限
  })

  it('采样值按小端序编码', async () => {
    const { bytes } = await viewOf(encodeWav([new Float32Array([1])], 8000))
    // 1 × 0x7fff = 32767 = 0x7FFF，小端序落盘为 FF 7F
    expect(bytes[44]).toBe(0xff)
    expect(bytes[45]).toBe(0x7f)
  })

  it('多个 chunk 按传入顺序连续写入', async () => {
    const { view } = await viewOf(encodeWav([new Float32Array([1]), new Float32Array([-1])], 8000))
    expect(view.getInt16(44, true)).toBe(32767)
    expect(view.getInt16(46, true)).toBe(-32768)
  })
})
