import { lazy, Suspense, useEffect, useState } from 'react'
import HomeView from './views/HomeView.jsx'
// DictationPanel / ReadingPanel 仍在此静态导入：训练状态机主体（trainingBody）留在 App，
// 它按状态渲染这两个组件，因此它们会随 App 进入首屏 chunk。若要进一步瘦身首屏，
// 需要把 trainingBody 连同其状态一起迁入 TrainingView（属独立改动）。
import DictationPanel from './DictationPanel.jsx'
import ReadingPanel from './ReadingPanel.jsx'
import { COMPLETED_STATES, VIEW_TITLES } from './viewUtils.js'
import { readJson, detailOf } from './api.js'

// 非首屏视图按需加载：打开页面只需首页的代码，其余面板（连同各自较重的子组件，
// 如 WeeklyPanel / P2Dashboard / DictationPanel / ReadingPanel）分别独立成 chunk。
const MaterialsView = lazy(() => import('./views/MaterialsView.jsx'))
const WeeklyView = lazy(() => import('./views/WeeklyView.jsx'))
const CandidatesView = lazy(() => import('./views/CandidatesView.jsx'))
const P2View = lazy(() => import('./views/P2View.jsx'))
const TrainingView = lazy(() => import('./views/TrainingView.jsx'))

const blankMaterial = { material_id: '', title: '', audio_path: '', transcript: '' }

function App() {
  const [health, setHealth] = useState('连接检查中…')
  const [materials, setMaterials] = useState([])
  const [view, setView] = useState('home')
  const [candidateStage, setCandidateStage] = useState('STAGE_1')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState(blankMaterial)
  const [message, setMessage] = useState('')
  const [comprehension, setComprehension] = useState({ rating: '30–50%', summary: '' })
  const [dictationContext, setDictationContext] = useState(null)
  const [dictationLoading, setDictationLoading] = useState(false)
  const [dictationError, setDictationError] = useState(false)
  const [firstListenPlayed, setFirstListenPlayed] = useState(false)
  const [loading, setLoading] = useState(true)
  const [homeError, setHomeError] = useState('')

  const refresh = () => {
    setLoading(true)
    setHomeError('')
    return fetch('/api/materials')
      .then((response) => {
        if (!response.ok) throw new Error('materials')
        return readJson(response)
      })
      .then((payload) => {
        setMaterials(payload)
        setLoading(false)
        return payload
      })
      .catch((error) => {
        setLoading(false)
        setHomeError('当前训练暂时无法加载，请检查连接后重试。')
        throw error
      })
  }

  useEffect(() => {
    fetch('/api/health')
      .then((response) => readJson(response))
      .then((healthPayload) => {
        setHealth(healthPayload.status === 'ok' ? '训练核心已就绪' : '训练核心异常')
        return refresh()
      })
      .catch(() => {
        setHealth('后端尚未启动')
        setLoading(false)
        setHomeError('当前训练暂时无法加载，请检查连接后重试。')
      })
  }, [])

  // 当前训练素材：优先最近一个进行中的素材，否则最近一篇（可能已完成）。
  const inProgress = materials.filter((material) => material.current_state && !COMPLETED_STATES.includes(material.current_state))
  const currentMaterial = inProgress[0] || materials[0] || null
  const currentCompleted = currentMaterial ? COMPLETED_STATES.includes(currentMaterial.current_state) : false

  const search = (event) => {
    event.preventDefault()
    fetch(`/api/materials/search?q=${encodeURIComponent(query)}`)
      .then((response) => readJson(response))
      .then(setMaterials)
      .catch(() => setMessage('素材搜索失败，请确认后端已启动。'))
  }

  const openMaterial = (materialId) => {
    fetch(`/api/materials/${encodeURIComponent(materialId)}`)
      .then((response) => {
        if (!response.ok) throw new Error('material')
        return readJson(response)
      })
      .then((payload) => {
        setSelected(payload)
        setDictationContext(null)
        setFirstListenPlayed(false)
        setView('training')
        setMessage('')
      })
      .catch(() => setMessage('无法打开素材详情。'))
  }

  const openMode = (key) => {
    if (key === 'weekly') { setView('weekly'); return }
    if (currentMaterial) openMaterial(currentMaterial.material_id)
    else setView('materials')
  }

  const retry = () => {
    setLoading(true)
    fetch('/api/health')
      .then((response) => readJson(response))
      .then((payload) => {
        setHealth(payload.status === 'ok' ? '训练核心已就绪' : '训练核心异常')
        return refresh()
      })
      .catch(() => {
        setHealth('后端尚未启动')
        setLoading(false)
        setHomeError('当前训练暂时无法加载，请检查连接后重试。')
      })
  }

  const refreshDictationContext = () => {
    if (!selected || !selected.current_state?.startsWith('DICTATION_PART_')) return
    setDictationLoading(true)
    setDictationError(false)
    fetch(`/api/materials/${selected.material_id}/dictation-context`)
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '无法加载听写上下文'))
        return payload
      })
      .then((context) => {
        setDictationContext(context)
        setDictationLoading(false)
      })
      .catch((error) => {
        setMessage(error.message)
        setDictationLoading(false)
        setDictationError(true)
      })
  }

  // 依赖项用预先取出的字符串，而不是 `selected && selected.current_state`：
  // 后者是表达式，react-hooks 无法做静态比对（会报 complex expression）。
  const selectedState = selected?.current_state

  // 刻意不把 refreshDictationContext 放进依赖数组——它是每次渲染都会重建的函数，
  // 加进去会让 effect 每次都重跑并触发请求循环；触发条件已由 selectedState 完整覆盖。
  // set-state-in-effect 提示的额外渲染源自该函数内部同步设置的 loading 标记，属保留行为。
  /* eslint-disable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    refreshDictationContext()
  }, [selectedState])
  /* eslint-enable react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

  const postTrainingEvent = (path, body) => {
    fetch(path, {
      method: 'POST',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '操作失败'))
        return payload
      })
      .then((progress) => {
        setSelected((current) => current ? { ...current, ...progress } : current)
        refresh().catch(() => {})
        setMessage('状态已更新。')
      })
      .catch((error) => setMessage(error.message))
  }

  const createMaterial = (event) => {
    event.preventDefault()
    const lines = form.transcript.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
    if (lines.length < 3) {
      setMessage('至少输入 3 行句子，系统才能分成三个 Part。')
      return
    }
    fetch('/api/materials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...form,
        transcript: lines.join(' '),
        timestamped_sentences: lines.map((text, index) => ({
          text, start_time: index * 8, end_time: (index + 1) * 8,
        })),
      }),
    })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '素材导入失败'))
        return payload
      })
      .then((payload) => {
        setForm(blankMaterial)
        setMessage('素材已导入，可以进入训练。')
        refresh().then(() => openMaterial(payload.material_id)).catch(() => {})
      })
      .catch((error) => setMessage(error.message))
  }

  const trainingBody = () => {
    if (!selected) return null
    const state = selected.current_state
    if (state === 'READY_FIRST_LISTEN') {
      return <div className="event-panel">
        <p>第一次完整盲听：完整播放整段素材，不显示字幕、原文或关键词。可以暂停，但请真实播放到结束。</p>
        <p className="muted">{firstListenPlayed ? '✅ 已完整播放到结尾，可以提交。' : '请在上方音频面板播放整段素材直到结束（进度条到末尾）。'}</p>
        <button className="primary" onClick={() => postTrainingEvent(`/api/materials/${selected.material_id}/first-listen/complete`)} disabled={!firstListenPlayed}>已完成首次盲听</button>
      </div>
    }
    if (state === 'FIRST_COMPREHENSION_CHECK' || state === 'SECOND_COMPREHENSION_CHECK') {
      const phase = state.startsWith('FIRST') ? 'FIRST' : 'SECOND'
      return <form className="event-form" onSubmit={(event) => {
        event.preventDefault()
        postTrainingEvent(`/api/materials/${selected.material_id}/comprehension-check`, {
          phase, self_rating: comprehension.rating, summary: comprehension.summary,
        })
      }}>
        <label>理解自评<select value={comprehension.rating} onChange={(event) => setComprehension({ ...comprehension, rating: event.target.value })}><option>&lt;30%</option><option>30–50%</option><option>50–70%</option><option>&gt;70%</option></select></label>
        <label>一句话总结<textarea required value={comprehension.summary} onChange={(event) => setComprehension({ ...comprehension, summary: event.target.value })} /></label>
        <button className="primary" type="submit">提交理解检查</button>
      </form>
    }
    if (state.startsWith('DICTATION_PART_')) {
      if (dictationLoading) return <p className="muted">正在加载听写上下文…</p>
      if (dictationError) {
        return <div className="event-panel">
          <p className="muted">听写上下文刷新失败，可重试。</p>
          <button className="primary" onClick={refreshDictationContext}>重新加载上下文</button>
        </div>
      }
      if (!dictationContext) {
        return <div className="event-panel">
          <p className="muted">听写上下文加载失败，可重试。</p>
          <button className="primary" onClick={refreshDictationContext}>重新加载</button>
        </div>
      }
      return <DictationPanel
        materialId={selected.material_id}
        context={dictationContext}
        onTransition={(payload) => {
          if (payload.next_action === 'SECOND_LISTEN') {
            setSelected((current) => current ? { ...current, current_state: payload.next_state } : current)
            setDictationContext(null)
          } else if (payload.next_context) {
            setDictationContext(payload.next_context)
          } else {
            refreshDictationContext()
          }
        }}
        onPartComplete={() => {
          const part = Number(state.slice(-1))
          return fetch(`/api/materials/${selected.material_id}/dictation-parts/${part}/complete`, { method: 'POST' })
            .then(async (response) => {
              const payload = await readJson(response)
              if (!response.ok) throw new Error(detailOf(payload, 'Part 完成失败'))
              return payload
            })
            .then((progress) => {
              setSelected((current) => current ? { ...current, ...progress } : current)
              setDictationContext(null)
              refresh().catch(() => {})
              setMessage('Part 完成，进入下一步。')
            })
            .catch((error) => {
              setMessage(error.message)
              throw error
            })
        }}
        onMessage={setMessage}
      />
    }
    if (state === 'SECOND_FULL_LISTEN') return <div className="event-panel">
      <p>第二次完整听：三个 Part 听写已全部完成。现在可以查看原文，完整听一遍全文。</p>
      <blockquote className="transcript">{selected.transcript}</blockquote>
      <button className="primary" onClick={() => postTrainingEvent(`/api/materials/${selected.material_id}/second-listen/complete`)}>已完成二次复听</button>
    </div>
    if (state === 'READING_AVAILABLE' || state === 'FULL_READING_ASSESSMENT') {
      if (state === 'READING_AVAILABLE') {
        const status = selected.reading_part_status || {}
        const partNo = [1, 2, 3].find((part) => !status[String(part)]) ?? 1
        return <ReadingPanel
          materialId={selected.material_id}
          scope="PART"
          partNo={partNo}
          sentences={selected.sentences.filter((sentence) => sentence.part_no === partNo)}
          onPartComplete={(progress) => { setSelected({ ...selected, ...progress }); setMessage('朗读 Part 完成。') }}
          onMessage={setMessage}
        />
      }
      return <ReadingPanel
        materialId={selected.material_id}
        scope="FULL"
        partNo={null}
        sentences={selected.sentences}
        onPartComplete={(progress) => { setSelected({ ...selected, ...progress }); setMessage('全文朗读验收通过，素材已完成。') }}
        onMessage={setMessage}
      />
    }
    if (state === 'LISTENING_COMPLETED' || state === 'FULLY_COMPLETED') {
      return <div className="event-panel">
        <p>本篇素材已完成。按学习节奏自动搜索下一篇（难度规则：一次只升级一个变量，周测稳定后由 Agent 决定是否升级）。</p>
        <button className="primary" onClick={searchNext} disabled={searching}>{searching ? '正在搜索素材并转录时间戳（约 1-2 分钟）…' : '获取下一篇素材'}</button>
      </div>
    }
    return <p>当前状态：{state}</p>
  }

  const [searching, setSearching] = useState(false)
  const searchNext = () => {
    setSearching(true)
    fetch('/api/materials/next', { method: 'POST' })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '搜索下一篇失败'))
        return payload
      })
      .then((payload) => {
        setSearching(false)
        onMaterialImported(payload.material_id)
        setMessage(payload.upgrade_available
          ? `已获取下一篇（周测稳定，难度档已升级）。来源：${payload.source_name}`
          : `已获取下一篇。来源：${payload.source_name}`)
      })
      .catch((error) => { setSearching(false); setMessage(error.message) })
  }

  const onMaterialImported = (materialId) => {
    fetch(`/api/materials/${encodeURIComponent(materialId)}`)
      .then((response) => readJson(response))
      .then((payload) => {
        setSelected(payload)
        setDictationContext(null)
        refresh()
      })
      .catch(() => setMessage('素材已导入，刷新列表后可见。'))
  }

  const skipMaterial = () => {
    if (!selected) return
    setMessage('正在跳过当前素材并搜索替代素材…')
    fetch(`/api/materials/${selected.material_id}/skip`, { method: 'POST' })
      .then(async (response) => {
        const payload = await readJson(response)
        if (!response.ok) throw new Error(detailOf(payload, '跳过失败'))
        return payload
      })
      .then(() => { refresh(); searchNext() })
      .catch((error) => setMessage('跳过失败：' + error.message))
  }

  const progressMatrix = () => {
    if (!selected) return null
    const dictationStatus = selected.dictation_part_status || {}
    const readingStatus = selected.reading_part_status || {}
    return (
      <div className="progress-matrix">
        {[1, 2, 3].map((part) => (
          <div className="matrix-cell" key={part}>
            <strong>Part {part}</strong>
            <span className={dictationStatus[String(part)] ? 'dot done' : 'dot todo'}>听写</span>
            <span className={readingStatus[String(part)] ? 'dot done' : 'dot locked'}>朗读</span>
          </div>
        ))}
      </div>
    )
  }

  const navItems = [
    { key: 'home', label: '首页' },
    { key: 'materials', label: '素材' },
    { key: 'weekly', label: '周测' },
    { key: 'candidates', label: '候选' },
    { key: 'p2', label: '仪表盘' },
  ]

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">LLA</div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <button key={item.key} className={view === item.key ? 'active' : ''} aria-current={view === item.key ? 'page' : undefined} onClick={() => setView(item.key)}>{item.label}</button>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">LANGUAGE TRAINING AGENT</p>
            <h1 className="page-title">{VIEW_TITLES[view] || '训练'}</h1>
          </div>
          <span className="status">{health}</span>
        </header>

        <Suspense fallback={<p className="muted">正在加载…</p>}>
          {view === 'home' && <HomeView
            health={health}
            loading={loading}
            homeError={homeError}
            currentMaterial={currentMaterial}
            currentCompleted={currentCompleted}
            onRetry={retry}
            onOpenMaterial={openMaterial}
            onNavigate={setView}
            onOpenMode={openMode}
          />}

          {view === 'materials' && <MaterialsView
            materials={materials}
            message={message}
            query={query}
            form={form}
            onQueryChange={setQuery}
            onSearch={search}
            onFormChange={setForm}
            onCreate={createMaterial}
            onOpenMaterial={openMaterial}
            onImported={onMaterialImported}
            onMessage={setMessage}
          />}

          {view === 'weekly' && <WeeklyView message={message} onMessage={setMessage} />}

          {view === 'candidates' && <CandidatesView
            stage={candidateStage}
            message={message}
            onStageChange={setCandidateStage}
            onMessage={setMessage}
            onImported={onMaterialImported}
          />}

          {view === 'p2' && <P2View message={message} onMessage={setMessage} />}

          {view === 'training' && <TrainingView
            selected={selected}
            message={message}
            progressMatrix={progressMatrix}
            trainingBody={trainingBody}
            onSkip={skipMaterial}
            onFirstListenEnd={setFirstListenPlayed}
          />}
        </Suspense>
      </main>
    </div>
  )
}

export default App
