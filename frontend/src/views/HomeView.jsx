import { TRAINING_MODES, stateText } from '../viewUtils.js'

// 首屏视图。与其他视图不同，本组件不做惰性加载——它是打开页面就看得到的视图，
// 拆成独立 chunk 只会增加一次额外请求。
export default function HomeView({
  health,
  loading,
  homeError,
  currentMaterial,
  currentCompleted,
  onRetry,
  onOpenMaterial,
  onNavigate,
  onOpenMode,
}) {
  return <>
    {health === '后端尚未启动' && <div className="notice error">后端尚未启动，无法加载训练数据。<button className="link-btn" onClick={onRetry}>重试</button></div>}
    <section className="home-section accent-training" aria-busy={loading}>
      <p className="section-label">当前训练</p>
      {loading ? (
        <div className="training-hero skeleton-block" role="status" aria-label="正在加载当前训练">
          <div className="sk-line sk-short"></div>
          <div className="sk-line sk-wide"></div>
          <div className="sk-line"></div>
        </div>
      ) : homeError ? (
        <div className="training-hero error-hero" role="alert">
          <div className="hero-meta"><span className="hero-state">加载失败</span></div>
          <h2>当前训练暂时不可用</h2>
          <p className="hero-context">{homeError}</p>
          <button className="primary" onClick={onRetry}>重试</button>
        </div>
      ) : currentMaterial ? (
        <div className="training-hero">
          <div className="hero-meta">
            <span className="hero-state">{stateText(currentMaterial.current_state)}</span>
            {currentMaterial.duration_seconds ? <span className="hero-muted">约 {Math.round(currentMaterial.duration_seconds / 60)} 分钟</span> : null}
            {currentMaterial.speech_rate_wpm ? <span className="hero-muted">{currentMaterial.speech_rate_wpm} wpm</span> : null}
          </div>
          <h2>{currentMaterial.title}</h2>
          <p className="hero-context">{currentMaterial.material_id}</p>
          <button className="primary" onClick={() => onOpenMaterial(currentMaterial.material_id)}>
            {currentCompleted ? '查看素材' : '继续训练'}
          </button>
        </div>
      ) : (
        <div className="training-hero empty-hero">
          <h2>还没有开始训练</h2>
          <p className="hero-context">导入或获取一篇素材，开始第一次盲听。</p>
          <button className="primary" onClick={() => onNavigate('materials')}>开始新素材</button>
        </div>
      )}
    </section>

    <section className="home-section accent-material">
      <p className="section-label">当前素材 / 新素材</p>
      <div className="material-cards">
        {currentMaterial ? (
          <button className="material-card" onClick={() => onOpenMaterial(currentMaterial.material_id)}>
            <span className="card-tag">当前素材</span>
            <strong>{currentMaterial.title}</strong>
            <p>{stateText(currentMaterial.current_state)}</p>
            <span className="card-action">{currentCompleted ? '查看 →' : '继续 →'}</span>
          </button>
        ) : (
          <div className="material-card is-empty">
            <span className="card-tag">当前素材</span>
            <strong>暂无素材</strong>
            <p>导入素材后，这里显示当前进度。</p>
          </div>
        )}
        <button className="material-card" onClick={() => onNavigate('candidates')}>
          <span className="card-tag">新素材</span>
          <strong>自动获取素材</strong>
          <p>搜索音质清晰的候选，确认后创建。</p>
          <span className="card-action">去获取 →</span>
        </button>
      </div>
    </section>

    <section className="home-section accent-modes">
      <p className="section-label">训练方式</p>
      <div className="mode-cards">
        {TRAINING_MODES.map((mode) => (
          <button key={mode.key} className="mode-card" onClick={() => onOpenMode(mode.key)}>
            <strong>{mode.name}</strong>
            <p>{mode.desc}</p>
          </button>
        ))}
      </div>
    </section>
  </>
}
