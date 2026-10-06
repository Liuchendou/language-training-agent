import WeeklyPanel from '../WeeklyPanel.jsx'

export default function WeeklyView({ message, onMessage }) {
  return <section className="module">
    <div className="section-heading light"><div><p className="eyebrow">周测 Gate</p><h2>每周质量闸门</h2><p className="muted">根据当周训练内容生成测试；低于 80% 或朗读未达标时不推荐进入下一轮，转入短强化包。</p></div></div>
    <WeeklyPanel onMessage={onMessage} />
    {message && <p className="notice">{message}</p>}
  </section>
}
