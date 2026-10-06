import { useEffect, useRef, useState } from 'react'
import { readJson, detailOf } from './api.js'

const POLL_INTERVAL_MS = 1500

const MODEL_OPTIONS = [
  { value: 'base', label: 'base · 更快（推荐）' },
  { value: 'small', label: 'small · 更准但更慢' },
]

const LANGUAGE_OPTIONS = [
  { value: '', label: '自动检测（推荐）' },
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
]

function ImportFromUrlPanel({ onImported, onMessage }) {
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [modelSize, setModelSize] = useState('base')
  const [language, setLanguage] = useState('')
  const [job, setJob] = useState(null)
  const [capabilities, setCapabilities] = useState(null)
  const [error, setError] = useState('')
  const [starting, setStarting] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    fetch('/api/materials/import-capabilities')
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '无法检测本地依赖'))
        return payload
      })
      .then(setCapabilities)
      .catch((err) => setCapabilities({ ready: false, problems: [err.message] }))
  }, [])

  // Poll the job until it reaches a terminal state, then stop cleanly.
  useEffect(() => {
    if (!job || job.status === 'DONE' || job.status === 'FAILED') return undefined
    timerRef.current = setTimeout(() => {
      fetch(`/api/materials/import-jobs/${encodeURIComponent(job.job_id)}`)
        .then(async (response) => {
          const payload = await readJson(response)
          if (!response.ok) throw new Error(detailOf(payload, '无法获取导入进度'))
          return payload
        })
        .then((payload) => {
          setJob(payload)
          if (payload.status === 'DONE') {
            onMessage(payload.message)
          }
        })
        .catch((err) => { setJob(null); setError(err.message) })
    }, POLL_INTERVAL_MS)
    return () => clearTimeout(timerRef.current)
  }, [job, onMessage])

  const start = (event) => {
    event.preventDefault()
    setError('')
    setStarting(true)
    fetch('/api/materials/import-from-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url.trim(),
        title: title.trim() || null,
        model_size: modelSize,
        language: language || null,
      }),
    })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '提交导入任务失败'))
        return payload
      })
      .then((payload) => {
        setStarting(false)
        setJob(payload)
        onMessage('已开始提取，正在下载与转写，请保持本页面打开。')
      })
      .catch((err) => { setStarting(false); setError(err.message) })
  }

  const busy = Boolean(job) && job.status !== 'DONE' && job.status !== 'FAILED'
  const percent = job ? Math.round((job.progress || 0) * 100) : 0

  return (
    <div className="import-url-panel">
      <p className="reading-title">用视频链接提取素材（B站 / YouTube / 小红书）</p>
      <p className="muted">
        粘贴视频页面链接，系统会自动下载音频、转码并做本地语音识别，生成带逐句时间戳的可训练素材。
        不需要自己准备音频文件或逐行文稿。
      </p>

      {capabilities && !capabilities.ready && (
        <p className="notice error">
          本机还缺少提取所需的组件，提交后会失败：
          <br />
          {capabilities.problems.map((problem) => <span key={problem}>· {problem}<br /></span>)}
        </p>
      )}

      <form className="import-form" onSubmit={start}>
        <input
          required
          placeholder="视频链接，如 https://www.bilibili.com/video/BV..."
          value={url}
          onChange={(event) => setUrl(event.target.value)}
        />
        <input
          placeholder="素材标题（可留空，默认取视频标题）"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <label className="inline-field">识别语言
          <select value={language} onChange={(event) => setLanguage(event.target.value)}>
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="inline-field">识别模型
          <select value={modelSize} onChange={(event) => setModelSize(event.target.value)}>
            {MODEL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <button className="primary" type="submit" disabled={busy || starting}>
          {busy ? '正在提取…' : '开始提取'}
        </button>
      </form>

      {job && (
        <div className="import-progress">
          <div className="import-progress-head">
            <strong>{job.stage_label || job.stage}</strong>
            <span className="muted">{percent}%</span>
          </div>
          <div className="progress-track" role="progressbar" aria-valuenow={percent} aria-valuemin="0" aria-valuemax="100">
            <div className="progress-fill" style={{ width: `${Math.max(2, percent)}%` }} />
          </div>
          <p className="muted">{job.message}</p>
          {job.status === 'DONE' && (
            <div className="dictation-actions">
              <button className="primary" onClick={() => onImported(job.material_id)}>进入训练</button>
              <span className="muted">
                {job.sentence_count} 句 · 约 {Math.round((job.duration_seconds || 0) / 60)} 分钟
              </span>
            </div>
          )}
          {job.status === 'FAILED' && (
            <p className="notice error">提取失败：{job.error}</p>
          )}
        </div>
      )}

      {error && <p className="notice error">{error}</p>}
    </div>
  )
}

export default ImportFromUrlPanel
