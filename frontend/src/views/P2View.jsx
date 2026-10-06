import P2Dashboard from '../P2Dashboard.jsx'

export default function P2View({ message, onMessage }) {
  return <section className="module">
    <div className="section-heading light"><div><p className="eyebrow">长期训练仪表盘（P2）</p><h2>观察与解释层</h2><p className="muted">只读视图：时长 / 首次理解曲线 / 周测趋势 / 朗读三维 / 记忆深化 / 难度历史。</p></div></div>
    <P2Dashboard onMessage={onMessage} />
    {message && <p className="notice">{message}</p>}
  </section>
}
