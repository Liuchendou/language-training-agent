import { useEffect, useRef, useState } from 'react'
import { readJson, detailOf } from './api.js'

const POLL_INTERVAL_MS = 1500

// Bilibili is the default because it stays reachable on restricted networks
// (VOA/BBC time out there). The VOA option remains for machines with a proxy.
const SOURCE_OPTIONS = [
  { value: 'bilibili', label: 'B站（国内可达）' },
  { value: 'voa', label: 'VOA（需可访问境外网络）' },
]

const STAGE_LABELS = {
  STAGE_1: 'Stage 1 · 慢速英语',
  STAGE_2: 'Stage 2 · 中等语速',
  STAGE_3: 'Stage 3 · 正常语速',
}

const DURATION_RANGES = [
  { value: 0, label: '5–15 分钟（推荐）', min: 300, max: 900 },
  { value: 1, label: '10–20 分钟', min: 600, max: 1200 },
  { value: 2, label: '15–20 分钟（原设定）', min: 900, max: 1200 },
  { value: 3, label: '不限时长', min: 180, max: 1800 },
]

function formatDuration(seconds) {
  const total = Math.round(Number(seconds) || 0)
  const minutes = Math.floor(total / 60)
  const rest = total % 60
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    return `${hours} 小时 ${minutes % 60} 分`
  }
  return `${minutes} 分 ${String(rest).padStart(2, '0')} 秒`
}

function formatPlayCount(count) {
  const value = Number(count) || 0
  if (value >= 10000) return `${(value / 10000).toFixed(1)} 万播放`
  return `${value} 播放`
}

function CandidatePanel({ stage, onStageChange, onMessage, onPrepared }) {
  const [source, setSource] = useState('bilibili')
  const [keyword, setKeyword] = useState('')
  const [rangeIndex, setRangeIndex] = useState(0)
  const [batch, setBatch] = useState(null)
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState(null)
  const [activeId, setActiveId] = useState(null)
  const timerRef = useRef(null)

  // Poll the import job until it reaches a terminal state, then stop cleanly.
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
          if (payload.status === 'DONE' || payload.status === 'FAILED') setActiveId(null)
        })
        .catch((error) => { setJob(null); setActiveId(null); onMessage(error.message) })
    }, POLL_INTERVAL_MS)
    return () => clearTimeout(timerRef.current)
  }, [job, onMessage])

  const search = () => {
    const range = DURATION_RANGES[rangeIndex]
    setBusy(true)
    setJob(null)
    setActiveId(null)
    fetch('/api/materials/candidate-search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source,
        speed_stage: stage,
        keyword: keyword.trim() || null,
        duration_min_seconds: range.min,
        duration_max_seconds: range.max,
        max_results: 12,
      }),
    })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '搜索候选失败'))
        return payload
      })
      .then((payload) => {
        setBatch(payload)
        setBusy(false)
        if (payload.source_error) {
          onMessage(`素材源访问失败，无法搜索候选：${payload.source_error}`)
          return
        }
        const total = payload.candidates.length
        onMessage(total
          ? `搜索完成：${total} 个候选（${payload.source}${payload.keyword ? ` · 关键词「${payload.keyword}」` : ''}）`
          : '所选时长区间内没有匹配的素材，可换个区间或关键词再试。')
      })
      .catch((error) => { setBusy(false); onMessage(error.message) })
  }

  const importCandidate = (candidate) => {
    setActiveId(candidate.provider_item_id)
    fetch('/api/materials/import-from-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: candidate.url, title: candidate.title || null }),
    })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '提交导入任务失败'))
        return payload
      })
      .then((payload) => {
        setJob(payload)
        onMessage('已开始提取，正在下载与转写，请保持本页面打开。')
      })
      .catch((error) => { setActiveId(null); onMessage(error.message) })
  }

  const importing = Boolean(job) && job.status !== 'DONE' && job.status !== 'FAILED'
  const percent = job ? Math.round((job.progress || 0) * 100) : 0
  const range = DURATION_RANGES[rangeIndex]

  return (
    <div className="weekly-panel">
      <p className="reading-title">先搜索素材，确认后再导入训练库</p>
      <p className="muted">
        搜索只列出候选（标题、时长、来源），选中后才会下载音频并做逐句转写。
        默认使用 B站素材源，它在本机网络下可正常访问。
      </p>

      <div className="weekly-meta">
        <label>素材来源
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            {SOURCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>难度阶段
          <select value={stage} onChange={(event) => onStageChange(event.target.value)}>
            <option value="STAGE_1">STAGE_1</option>
            <option value="STAGE_2">STAGE_2</option>
            <option value="STAGE_3">STAGE_3</option>
          </select>
        </label>
        <label>时长区间
          <select value={rangeIndex} onChange={(event) => setRangeIndex(Number(event.target.value))}>
            {DURATION_RANGES.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      <form className="search-bar" onSubmit={(event) => { event.preventDefault(); search() }}>
        <input
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder={source === 'bilibili'
            ? '关键词（可留空，默认按阶段搜索慢速英语/新闻/故事）'
            : '关键词（VOA 按节目区搜索，可留空）'}
        />
        <button className="primary" type="submit" disabled={busy}>
          {busy ? '正在搜索…' : '搜索候选素材'}
        </button>
      </form>
      <p className="search-hint">
        当前：{STAGE_LABELS[stage]} · {range.label}
        {source === 'bilibili' && ' · B站搜索需用中文关键词，例如「慢速英语」「英语听力」'}
      </p>

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
              <button className="primary" onClick={() => onPrepared(job.material_id)}>进入训练</button>
              <span className="muted">
                {job.sentence_count} 句 · 约 {Math.round((job.duration_seconds || 0) / 60)} 分钟
              </span>
            </div>
          )}
          {job.status === 'FAILED' && <p className="notice error">导入失败：{job.error}</p>}
        </div>
      )}

      {batch && (
        <div className="weekly-items">
          {batch.source_error && (
            <p className="notice error">
              素材源访问失败，本次未搜到任何候选：{batch.source_error}
              <br />这不代表「没有合适的候选」。可换用 B站来源后重试。
            </p>
          )}
          {batch.candidates.length ? batch.candidates.map((candidate) => (
            <div className="weekly-item" key={candidate.provider_item_id}>
              <span>▶</span>
              <div className="candidate-info">
                <strong>{candidate.title}</strong>
                <p className="muted">
                  {formatDuration(candidate.duration_seconds)}
                  {candidate.author ? ` · ${candidate.author}` : ''}
                  {candidate.play_count ? ` · ${formatPlayCount(candidate.play_count)}` : ''}
                </p>
              </div>
              <button
                className="primary"
                onClick={() => importCandidate(candidate)}
                disabled={importing || Boolean(activeId)}
              >
                {activeId === candidate.provider_item_id && importing ? '导入中…' : '导入此素材'}
              </button>
            </div>
          )) : !batch.source_error && <p className="muted">无候选。可调整时长区间或关键词后重试。</p>}
        </div>
      )}
    </div>
  )
}

export default CandidatePanel
