/**
 * Inter Migration Intelligence — PDF Report Generator
 * Usage: node generate_report.js <output.pdf> <data.json>
 * Setup: npm install puppeteer && npm install pdf-lib
 */

const fs = require("fs");

const outPath = process.argv[2];
const dataPath = process.argv[3];

if (!outPath || !dataPath) {
  console.error("Usage: node generate_report.js <output.pdf> <data.json>");
  process.exit(1);
}
if (!fs.existsSync(dataPath)) {
  console.error("Data file not found: " + dataPath);
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(dataPath, "utf-8"));
console.log(
  `📄 Data loaded: ${data.monthly?.length || 0} months · ${data.topOccupations?.length || 0} occupations`,
);
console.log(
  `   Pathways: ${data.pathways?.length || 0} (dummy=${data.pathways_is_dummy}), Approvals: ${data.approvals?.length || 0} (dummy=${data.approvals_is_dummy})`,
);
if (data.approvals && data.approvals.length > 0) {
  console.log(`   First approval: ${JSON.stringify(data.approvals[0])}`);
} else {
  console.log("   ⚠️ NO APPROVALS FOUND!");
}

const C = {
  navy: "#1E2761",
  ice: "#CADCFC",
  white: "#FFFFFF",
  dark: "#0D1B3E",
  teal: "#0891B2",
  green: "#059669",
  amber: "#D97706",
  red: "#DC2626",
  muted: "#94A3B8",
  light: "#E8EFF9",
  border: "#CBD5E1",
  text: "#1E293B",
  subtext: "#475569",
};
const STATE_COLORS = {
  NSW: "#2A8BFF",
  VIC: "#8B5CF6",
  QLD: "#F59E0B",
  SA: "#EF4444",
  WA: "#10B981",
  TAS: "#06B6D4",
  NT: "#F97316",
  ACT: "#EC4899",
};

const BASE_CSS = `
  *{margin:0;padding:0;box-sizing:border-box;}
  body{width:1280px;height:720px;overflow:hidden;font-family:'Segoe UI',Calibri,Arial,sans-serif;font-size:14px;color:${C.text};}
  .slide{width:1280px;height:720px;position:relative;overflow:hidden;}
  .header-bar{position:absolute;top:0;left:0;right:0;height:52px;background:${C.navy};display:flex;align-items:center;padding:0 20px;gap:10px;}
  .logo-dot{width:28px;height:28px;border-radius:50%;background:${C.teal};display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;color:white;flex-shrink:0;}
  .logo-name{font-size:13px;font-weight:700;color:white;}
  .slide-title{position:absolute;top:52px;left:0;right:0;padding:14px 36px 0;font-size:26px;font-weight:800;color:${C.navy};}
  .slide-subtitle{position:absolute;top:100px;left:0;right:0;padding:0 36px;font-size:12px;color:${C.muted};}
  .content-area{position:absolute;top:128px;left:36px;right:36px;bottom:40px;}
  .footer{position:absolute;bottom:0;left:0;right:0;height:28px;background:${C.navy};display:flex;align-items:center;justify-content:space-between;padding:0 20px;font-size:10px;color:${C.ice};}
  .stat-row{display:flex;gap:12px;}
  .stat-box{flex:1;background:${C.light};border-radius:8px;padding:14px 16px 12px;border-left:4px solid var(--accent);box-shadow:0 1px 4px rgba(0,0,0,0.08);}
  .stat-value{font-size:28px;font-weight:800;color:var(--accent);line-height:1;}
  .stat-label{font-size:11px;color:${C.subtext};margin-top:6px;line-height:1.3;}
  .card{background:white;border-radius:10px;padding:16px;border:1px solid ${C.border};box-shadow:0 1px 4px rgba(0,0,0,0.06);}
  .card-title{font-size:12px;font-weight:700;color:${C.navy};margin-bottom:12px;}
  .data-table{width:100%;border-collapse:collapse;font-size:11px;}
  .data-table th{background:${C.navy};color:white;padding:6px 8px;text-align:left;font-weight:700;font-size:10px;}
  .data-table td{padding:5px 8px;border-bottom:1px solid #F1F5F9;}
  .data-table tr:nth-child(even) td{background:#F8FAFC;}
  .progress-track{background:#E2E8F0;border-radius:4px;height:8px;}
  .progress-fill{height:100%;border-radius:4px;}
  .shortage-row{display:flex;align-items:center;gap:8px;padding:5px 8px;border-bottom:1px solid #F1F5F9;font-size:11px;}
  .shortage-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
`;

function header() {
  return `<div class="header-bar"><div class="logo-dot">I</div><span class="logo-name">Inter Intelligence</span></div>`;
}
function footer(n) {
  const now = new Date().toLocaleDateString("en-AU", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return `<div class="footer"><span>Inter Migration Intelligence · Confidential · ${now}</span><span>${n}</span></div>`;
}

function slideCover() {
  const p = data.profile || {},
    s = data.summary || {};
  const now = new Date().toLocaleDateString("en-AU", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const stats = [
    {
      v: s.eoi_pool ? (s.eoi_pool / 1000000).toFixed(1) + "M" : "—",
      l: "Active EOI Pool",
      c: C.teal,
    },
    { v: s.shortage_occupations ?? "—", l: "Occupations", c: "#8B5CF6" },
    { v: "8", l: "States", c: C.green },
    {
      v: "Visa " + (p.visa_type || "491"),
      l: "Client Visa Target",
      c: C.amber,
    },
  ];
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  ${BASE_CSS}
  .cover{width:1280px;height:720px;display:flex;overflow:hidden;}
  .cover-left{width:440px;flex-shrink:0;background:${C.navy};display:flex;flex-direction:column;padding:48px 40px;position:relative;}
  .cover-right{flex:1;background:${C.dark};display:flex;flex-direction:column;justify-content:center;padding:48px 52px;gap:32px;}
  .stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
  .stat-card{background:#0D2B4E;border-radius:10px;padding:18px 20px;border:1px solid rgba(255,255,255,0.08);}
  .cover-footer{position:absolute;bottom:0;left:0;right:0;height:28px;background:#0A0F1E;display:flex;align-items:center;justify-content:center;font-size:10px;color:${C.muted};}
  </style></head><body>
  <div class="cover">
    <div class="cover-left">
      <div style="position:absolute;left:0;top:0;bottom:0;width:8px;background:${C.teal};"></div>
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:48px;">
        <div style="width:44px;height:44px;border-radius:50%;background:${C.teal};display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:800;color:white;">I</div>
        <span style="font-size:16px;font-weight:700;color:white;">Inter Intelligence</span>
      </div>
      <div style="font-size:36px;font-weight:800;color:white;line-height:1.15;margin-bottom:10px;">Migration<br>Intelligence</div>
      <div style="font-size:24px;color:${C.ice};font-weight:300;margin-bottom:32px;">Client Report</div>
      <div style="width:60px;height:3px;background:${C.teal};margin-bottom:20px;"></div>
      <div style="font-size:12px;color:${C.muted};margin-bottom:8px;">${now}</div>
      <div style="font-size:11px;color:#475569;line-height:1.8;">${p.occupation || "—"}<br>Visa ${p.visa_type || "—"} · ${p.state || "—"} · ${p.points || "—"} pts<br>Powered by Inter Migration Intelligence Platform</div>
    </div>
    <div class="cover-right">
      <div style="font-size:16px;font-weight:700;color:white;">Platform snapshot</div>
      <div class="stats-grid">
        ${stats.map((s) => `<div class="stat-card"><div style="font-size:36px;font-weight:800;color:${s.c};line-height:1;margin-bottom:6px;">${s.v}</div><div style="font-size:11px;color:${C.ice};">${s.l}</div></div>`).join("")}
      </div>
    </div>
  </div>
  <div class="cover-footer">CONFIDENTIAL · For client use only</div>
  </body></html>`;
}

function slideEOI() {
  const monthly = data.monthly || [],
    recent = monthly.slice(-6),
    latest = monthly[monthly.length - 1] || {};
  const totalInv = monthly.reduce((s, m) => s + (m.invitations || 0), 0);
  const totalPool = monthly.reduce((s, m) => s + (m.pool || 0), 0);
  const rate = totalPool > 0 ? Math.round((totalInv / totalPool) * 100) : 0;
  const maxVal = Math.max(
    ...recent.map((m) => Math.max(m.pool || 0, m.invitations || 0)),
    1,
  );
  const topOccs = (data.topOccupations || []).slice(0, 6);
  const rangeLabel = data.allData
    ? `All ${data.totalMonths} months`
    : `Last ${data.months} months`;
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>${BASE_CSS}</style></head><body>
  <div class="slide" style="background:#F8FAFC;">
    ${header()}
    <div class="slide-title">EOI Trends Overview</div>
    <div class="slide-subtitle">SkillSelect activity · ${rangeLabel} · Snapshot: ${data.summary?.latest_snapshot || "latest"}</div>
    <div class="content-area">
      <div class="stat-row" style="margin-bottom:14px;">
        <div class="stat-box" style="--accent:${C.teal}"><div class="stat-value">${(latest.pool || 0).toLocaleString()}</div><div class="stat-label">EOI Pool<br>Latest Month</div></div>
        <div class="stat-box" style="--accent:${C.green}"><div class="stat-value">${(latest.invitations || 0).toLocaleString()}</div><div class="stat-label">Invitations<br>Latest Month</div></div>
        <div class="stat-box" style="--accent:#8B5CF6"><div class="stat-value">${rate}%</div><div class="stat-label">Overall<br>Invitation Rate</div></div>
        <div class="stat-box" style="--accent:${C.amber}"><div class="stat-value">${monthly.length}</div><div class="stat-label">Months of<br>Data</div></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
        <div class="card">
          <div class="card-title">Monthly EOI Activity (Last 6 Months)</div>
          ${
            recent.length > 0
              ? `
          <div style="display:flex;gap:4px;align-items:flex-end;height:150px;padding:0 4px;">
            ${recent
              .map((m) => {
                const pH = Math.round(((m.pool || 0) / maxVal) * 130);
                const iH = Math.round(((m.invitations || 0) / maxVal) * 130);
                return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;"><div style="display:flex;align-items:flex-end;gap:2px;height:130px;"><div style="width:14px;height:${pH}px;background:${C.teal};border-radius:2px 2px 0 0;min-height:2px;"></div><div style="width:14px;height:${iH}px;background:${C.green};border-radius:2px 2px 0 0;min-height:2px;"></div></div><div style="font-size:9px;color:${C.muted};text-align:center;">${(m.month || "").slice(0, 7)}</div></div>`;
              })
              .join("")}
          </div>
          <div style="display:flex;gap:16px;margin-top:8px;">
            <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:${C.subtext};"><div style="width:10px;height:10px;background:${C.teal};border-radius:2px;"></div>Pool</div>
            <div style="display:flex;align-items:center;gap:4px;font-size:10px;color:${C.subtext};"><div style="width:10px;height:10px;background:${C.green};border-radius:2px;"></div>Invitations</div>
          </div>`
              : `<div style="color:${C.muted};font-size:12px;padding:20px;text-align:center;">No monthly data available</div>`
          }
        </div>
        <div class="card">
          <div class="card-title">Top Occupations by EOI Volume</div>
          ${topOccs.length > 0 ? `<table class="data-table"><thead><tr><th>ANZSCO</th><th>Occupation</th><th>Pool</th><th>Inv. Rate</th></tr></thead><tbody>${topOccs.map((o) => `<tr><td style="color:${C.teal};font-weight:700;font-family:monospace;">${o.anzsco_code || ""}</td><td>${(o.occupation_name || "").slice(0, 26)}</td><td style="font-weight:700;color:${C.navy};">${(o.pool || 0).toLocaleString()}</td><td style="color:${C.green};font-weight:700;">${o.invitation_rate ? Math.round(o.invitation_rate * 100) + "%" : "—"}</td></tr>`).join("")}</tbody></table>` : `<div style="color:${C.muted};font-size:12px;padding:20px;text-align:center;">No occupation data</div>`}
        </div>
      </div>
    </div>
    ${footer(2)}
  </div></body></html>`;
}

function slideShortage() {
  const hm = data.heatmap || {},
    states = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];
  const counts = hm.state_shortage_counts || {};
  const maxCount = Math.max(...states.map((s) => counts[s] || 0), 1);
  const topS = (hm.records || [])
    .filter((r) => r.national === 1)
    .sort((a, b) => b.shortage_state_count - a.shortage_state_count)
    .slice(0, 8);
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>${BASE_CSS}</style></head><body>
  <div class="slide" style="background:#F8FAFC;">
    ${header()}
    <div class="slide-title">Occupation Shortage Analysis</div>
    <div class="slide-subtitle">DESE OSL national &amp; state shortage ratings · ${hm.year || 2025}</div>
    <div class="content-area">
      <div class="stat-row" style="margin-bottom:14px;">
        <div class="stat-box" style="--accent:${C.red}"><div class="stat-value">${hm.national_shortage_count || 0}</div><div class="stat-label">National Shortage<br>Occupations</div></div>
        <div class="stat-box" style="--accent:${C.amber}"><div class="stat-value">${hm.national_shortage_pct || 0}%</div><div class="stat-label">Shortage Rate</div></div>
        <div class="stat-box" style="--accent:${C.teal}"><div class="stat-value">${hm.total_occupations || 0}</div><div class="stat-label">Total Occupations<br>Tracked</div></div>
        <div class="stat-box" style="--accent:#8B5CF6"><div class="stat-value">${states.filter((s) => (counts[s] || 0) > 0).length}</div><div class="stat-label">States With<br>Shortages</div></div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;">
        <div class="card">
          <div class="card-title">Shortage Occupations by State</div>
          <div style="display:flex;gap:8px;align-items:flex-end;height:180px;padding:8px 4px 0;">
            ${states
              .map((s) => {
                const count = counts[s] || 0;
                const barH = Math.round((count / maxCount) * 160);
                const col = STATE_COLORS[s] || C.teal;
                return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;"><div style="font-size:10px;font-weight:700;color:${col};">${count}</div><div style="width:100%;height:${barH}px;background:${col};border-radius:4px 4px 0 0;min-height:3px;"></div><div style="font-size:10px;color:${C.muted};font-weight:600;">${s}</div></div>`;
              })
              .join("")}
          </div>
        </div>
        <div class="card">
          <div class="card-title">Top National Shortage Occupations</div>
          ${
            topS.length > 0
              ? topS
                  .map((r) => {
                    const col =
                      r.shortage_state_count >= 6
                        ? C.red
                        : r.shortage_state_count >= 3
                          ? C.amber
                          : C.green;
                    return `<div class="shortage-row"><div class="shortage-dot" style="background:${col};"></div><div style="flex:1;">${(r.occupation_name || "").slice(0, 34)}</div><div style="font-size:10px;font-weight:700;color:${col};min-width:55px;text-align:right;">${r.shortage_state_count}/8 states</div></div>`;
                  })
                  .join("")
              : `<div style="color:${C.muted};font-size:12px;padding:20px;text-align:center;">No shortage data</div>`
          }
        </div>
      </div>
    </div>
    ${footer(3)}
  </div></body></html>`;
}

function slidePathway() {
  const items = data.pathways || [];
  const p = data.profile || {};
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>${BASE_CSS}</style></head><body>
  <div class="slide" style="background:#F8FAFC;">
    ${header()}
    <div class="slide-title">Pathway Recommendations</div>
    <div class="slide-subtitle">GBM match scoring · Visa + state combinations · Profile: ${p.points || "—"} pts</div>
    <div class="content-area">
      <div style="display:grid;grid-template-columns:300px 1fr;gap:20px;height:100%;">
        <div class="card" style="background:${C.navy};color:white;display:flex;flex-direction:column;justify-content:center;padding:24px;">
          <div style="font-size:14px;color:${C.ice};margin-bottom:8px;">Target Occupation</div>
          <div style="font-size:18px;font-weight:700;margin-bottom:24px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:12px;">${p.occupation || "—"}</div>
          <div style="font-size:14px;color:${C.ice};margin-bottom:8px;">Base Points</div>
          <div style="font-size:32px;font-weight:800;color:${C.teal};">${p.points || 0}</div>
        </div>
        <div class="card">
          <div class="card-title">Top Recommended Pathways</div>
          ${
            items.length > 0
              ? `
          <table class="data-table">
            <thead><tr><th>Rank</th><th>Visa</th><th>State</th><th>Match Score</th><th>Requirements Preview</th></tr></thead>
            <tbody>
              ${items
                .slice(0, 6)
                .map(
                  (it, i) => `
                <tr>
                  <td style="font-weight:700;color:${C.muted};">#${i + 1}</td>
                  <td style="font-weight:700;color:${C.teal};">${it.visa || "—"}</td>
                  <td style="font-weight:700;color:${C.navy};">${it.state || "—"}</td>
                  <td>
                    <div style="display:flex;align-items:center;gap:6px;">
                      <div class="progress-track" style="flex:1;"><div class="progress-fill" style="width:${Math.round(it.score * 100)}%;background:${C.teal};"></div></div>
                      <span style="font-weight:700;color:${C.teal};min-width:30px;">${Math.round(it.score * 100)}%</span>
                    </div>
                  </td>
                  <td style="color:${C.subtext};font-size:9px;max-width:240px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${it.requirements || "Standard requirements apply"}</td>
                </tr>`,
                )
                .join("")}
            </tbody>
          </table>`
              : `<div style="color:${C.muted};font-size:12px;padding:20px;text-align:center;">No pathways generated for this profile</div>`
          }
        </div>
      </div>
    </div>
    ${footer(4)}
  </div></body></html>`;
}

function slideApproval() {
  const items = data.approvals || [];
  const p = data.profile || {};
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>${BASE_CSS}</style></head><body>
  <div class="slide" style="background:#F8FAFC;">
    ${header()}
    <div class="slide-title">Approval Probability (What-If)</div>
    <div class="slide-subtitle">XGBoost cross-state prediction · ${p.visa_type || "491"} cohort · ${p.points || "—"} pts profile</div>
    <div class="content-area">
      <div class="card" style="height:100%;">
        <div class="card-title">Estimated Approval Probability by State</div>
        <div style="display:flex;flex-direction:column;gap:12px;padding:10px 20px;">
          ${
            items.length > 0
              ? items
                  .map((it) => {
                    const prob = it.prob || 0;
                    const col =
                      prob > 0.7 ? C.green : prob > 0.4 ? C.amber : C.red;
                    return `
              <div style="display:flex;align-items:center;gap:15px;">
                <div style="width:40px;font-weight:800;color:${C.navy};">${it.state}</div>
                <div class="progress-track" style="flex:1;height:12px;"><div class="progress-fill" style="width:${Math.round(prob * 100)}%;background:${col};"></div></div>
                <div style="width:50px;font-weight:800;color:${col};text-align:right;">${Math.round(prob * 100)}%</div>
                <div style="width:80px;font-size:10px;color:${C.muted};">${prob > 0.7 ? "High Prob." : prob > 0.4 ? "Medium Prob." : "Low Prob."}</div>
              </div>`;
                  })
                  .join("")
              : `<div style="color:${C.muted};font-size:12px;padding:20px;text-align:center;">No approval analysis found</div>`
          }
        </div>
        <div style="margin-top:24px;background:#F1F5F9;border-radius:6px;padding:12px 16px;">
          <p style="font-size:10px;color:${C.subtext};line-height:1.5;"><strong>Note:</strong> These probabilities are predictions based on historical EOI activity, quota allocations, and the current profile match. This is not a legal guarantee of outcome.</p>
        </div>
      </div>
    </div>
    ${footer(5)}
  </div></body></html>`;
}

function slideSummary() {
  const p = data.profile || {},
    hm = data.heatmap || {},
    s = data.summary || {};
  const findings = [
    {
      title: "EOI Activity",
      color: C.teal,
      body: `${data.monthly?.length || 0} months of SkillSelect data. Active pool: ${(s.eoi_pool || 0).toLocaleString()} EOIs. Latest snapshot: ${s.latest_snapshot || "N/A"}.`,
    },
    {
      title: "Shortage Outlook",
      color: C.amber,
      body: `${hm.national_shortage_count || 0} occupations nationally in shortage (${hm.national_shortage_pct || 0}% of ${hm.total_occupations || 0} tracked). Source: DESE OSL ${hm.year || 2025}.`,
    },
    {
      title: "Pathway Analysis",
      color: "#8B5CF6",
      body: `Pathway predictions available after Sprint 4 ML training. Profile: Visa ${p.visa_type || "—"} · ${p.state || "—"} · ${p.points || "—"} pts.`,
    },
    {
      title: "Approval Analysis",
      color: C.green,
      body: `State-by-state approval probability available after Sprint 4 XGBoost model training. Will cover all 8 Australian states.`,
    },
  ];
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  ${BASE_CSS}
  .summary{width:1280px;height:720px;display:flex;overflow:hidden;}
  .s-left{width:420px;flex-shrink:0;background:${C.navy};display:flex;flex-direction:column;padding:48px 40px;position:relative;}
  .s-right{flex:1;background:${C.dark};padding:48px 48px;display:flex;flex-direction:column;gap:16px;}
  .finding{background:#0D2B4E;border-radius:8px;padding:14px 18px;border:1px solid rgba(255,255,255,0.08);border-left:4px solid var(--accent);}
  .s-footer{position:absolute;bottom:0;left:0;right:0;height:28px;background:#0A0F1E;display:flex;align-items:center;justify-content:center;font-size:10px;color:${C.muted};}
  </style></head><body>
  <div class="summary">
    <div class="s-left">
      <div style="position:absolute;left:0;top:0;bottom:0;width:8px;background:${C.teal};"></div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:32px;">
        <div style="width:32px;height:32px;border-radius:50%;background:${C.teal};display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;color:white;">I</div>
        <span style="font-size:13px;font-weight:700;color:white;">Inter Intelligence</span>
      </div>
      <div style="font-size:32px;font-weight:800;color:white;line-height:1.2;margin-bottom:12px;">Summary &amp;<br>Next Steps</div>
      <div style="width:50px;height:3px;background:${C.teal};margin-bottom:20px;"></div>
      <div style="font-size:11px;color:${C.ice};line-height:1.8;"><strong style="color:white;">Client Profile</strong><br>${p.occupation || "—"}<br>Visa ${p.visa_type || "—"} · ${p.state || "—"}<br>${p.points || "—"} points<br><br>Contact your Inter Studies<br>consultant to discuss these<br>findings in detail.</div>
    </div>
    <div class="s-right">
      <div style="font-size:18px;font-weight:700;color:white;">Key Findings</div>
      ${findings.map((f) => `<div class="finding" style="--accent:${f.color}"><div style="font-size:13px;font-weight:700;color:white;margin-bottom:5px;">${f.title}</div><div style="font-size:11px;color:${C.ice};line-height:1.5;">${f.body}</div></div>`).join("")}
    </div>
    <div class="s-footer">Inter Migration Intelligence · Confidential · For client use only</div>
  </div>
  </body></html>`;
}

// ── Render PDF ─────────────────────────────────────────────────

async function main() {
  console.log("\n🖨  Rendering HTML PDF via Puppeteer...");
  console.time("⏱️  TOTAL_TIME");

  let puppeteer;
  try {
    puppeteer = require("puppeteer");
  } catch (e) {
    console.error("❌ puppeteer not found. Run: npm install puppeteer");
    process.exit(1);
  }

  let browser;
  try {
    // ===== STEP 1: Launch Browser =====
    console.time("⏱️  BROWSER_LAUNCH");
    console.log("🚀 Launching browser...");
    browser = await puppeteer.launch({
      headless: true,
      executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-software-rasterizer",
        "--disable-extensions",
      ],
    });
    console.timeEnd("⏱️  BROWSER_LAUNCH");

    // ===== STEP 2: Create Page =====
    console.time("⏱️  PAGE_CREATION");
    console.log("📄 Creating new page...");
    const page = await browser.newPage();
    await page.setJavaScriptEnabled(false);
    console.timeEnd("⏱️  PAGE_CREATION");
    console.log("✅ Page created.");

    // ===== STEP 3: Generate Slide HTML =====
    console.time("⏱️  SLIDE_GENERATION");
    console.log("🎨 Generating slide HTML...");
    const slidesHtml = [
      slideCover(),
      slideEOI(),
      slideShortage(),
      slidePathway(),
      slideApproval(),
      slideSummary(),
    ];
    console.timeEnd("⏱️  SLIDE_GENERATION");

    // ===== STEP 4: Stitch Slides =====
    console.time("⏱️  SLIDE_STITCHING");
    console.log("🧵 Stitching slides...");
    let joinedSlides = slidesHtml
      .map((html) => {
        const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
        return bodyMatch ? bodyMatch[1] : html;
      })
      .join("");
    console.timeEnd("⏱️  SLIDE_STITCHING");

    // ===== STEP 5: Build Full HTML =====
    console.time("⏱️  HTML_BUILD");
    console.log("🔨 Building full HTML...");
    const fullHtml = `<!DOCTYPE html><html><head><meta charset="utf-8">
      <style>
        ${BASE_CSS}
        @media print {
          body { 
            width: 1280px !important;
            height: auto !important;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact; 
          }
          .cover:not(:last-child), .slide:not(:last-child), .summary:not(:last-child) { 
            page-break-after: always;
          }
          .cover, .slide, .summary { 
            width: 1280px !important;
            height: 720px !important;
            position: relative !important;
            overflow: hidden !important;
            box-sizing: border-box !important;
          }
        }
        /* Cover specific styles */
        .cover{width:1280px;height:720px;display:flex;overflow:hidden;}
        .cover-left{width:440px;flex-shrink:0;background:${C.navy};display:flex;flex-direction:column;padding:48px 40px;position:relative;}
        .cover-right{flex:1;background:${C.dark};display:flex;flex-direction:column;justify-content:center;padding:48px 52px;gap:32px;}
        .stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
        .stat-card{background:#0D2B4E;border-radius:10px;padding:18px 20px;border:1px solid rgba(255,255,255,0.08);}
        .cover-footer{position:absolute;bottom:0;left:0;right:0;height:28px;background:#0A0F1E;display:flex;align-items:center;justify-content:center;font-size:10px;color:${C.muted};}
        /* Summary specific styles */
        .summary{width:1280px;height:720px;display:flex;overflow:hidden;}
        .s-left{width:420px;flex-shrink:0;background:${C.navy};display:flex;flex-direction:column;padding:48px 40px;position:relative;}
        .s-right{flex:1;background:${C.dark};padding:48px 48px;display:flex;flex-direction:column;gap:16px;}
        .finding{background:#0D2B4E;border-radius:8px;padding:14px 18px;border:1px solid rgba(255,255,255,0.08);border-left:4px solid var(--accent);}
        .s-footer{position:absolute;bottom:0;left:0;right:0;height:28px;background:#0A0F1E;display:flex;align-items:center;justify-content:center;font-size:10px;color:${C.muted};}
      </style></head><body style="margin:0;padding:0;background:white;">
      ${joinedSlides}
    </body></html>`;
    console.timeEnd("⏱️  HTML_BUILD");

    // ===== STEP 6: Set Page Content =====
    console.time("⏱️  PAGE_CONTENT_SET");
    console.log("🛠  Setting page content...");
    await page.setContent(fullHtml, {
      waitUntil: "domcontentloaded",
      timeout: 15000,
    });
    console.timeEnd("⏱️  PAGE_CONTENT_SET");

    // ===== STEP 7: Generate PDF =====
    console.time("⏱️  PDF_GENERATION");
    console.log("🎨 Generating PDF bytes...");
    const pdfBytes = await page.pdf({
      width: "1280px",
      height: "720px",
      printBackground: true,
      margin: { top: 0, right: 0, bottom: 0, left: 0 },
    });
    console.timeEnd("⏱️  PDF_GENERATION");

    // ===== STEP 8: Save File =====
    console.time("⏱️  FILE_WRITE");
    console.log("💾 Writing PDF to disk...");
    fs.writeFileSync(outPath, pdfBytes);
    console.timeEnd("⏱️  FILE_WRITE");

    console.log(
      `\n✅ PDF saved: ${outPath} (${(pdfBytes.length / 1024).toFixed(1)} KB)`,
    );
  } catch (err) {
    console.error("❌ PDF generation error:", err.message);
    process.exit(1);
  } finally {
    if (browser) {
      console.log("🔒 Closing browser...");
      await browser.close();
    }
    console.timeEnd("⏱️  TOTAL_TIME");
    console.log("\n📊 Timing breakdown complete!\n");
  }
}

main().catch((e) => {
  console.error("❌ Fatal:", e.message);
  process.exit(1);
});
