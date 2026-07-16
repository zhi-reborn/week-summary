import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <main className="home-page page-shell">
      <div className="home-nav"><div className="issue-mark">WEEKLY / LOCAL / 01</div><Link to="/settings">模型设置</Link></div>
      <section className="hero-grid">
        <div>
          <p className="eyebrow">私有模型 · 本地文件 · Word 原版式</p>
          <h1 aria-label="智能周报汇总系统">智能周报<br />汇总系统</h1>
        </div>
        <div className="hero-copy">
          <p>把团队周报从复制粘贴，变成一条可核验、可校审、可重复的生产流程。</p>
          <Link aria-label="新建周报汇总" className="primary-action" role="button" to="/tasks/new/upload">新建周报汇总 <span>↗</span></Link>
        </div>
      </section>
      <section className="principles" aria-label="产品特性">
        <article><strong>01</strong><h2>识别</h2><p>从合并 TXT 中定位每位成员及原文行号。</p></article>
        <article><strong>02</strong><h2>提炼</h2><p>使用内网私有模型逐人分析并跨人聚合。</p></article>
        <article><strong>03</strong><h2>回填</h2><p>只修改模板目标区域，保留 Word 原始结构。</p></article>
      </section>
    </main>
  );
}
