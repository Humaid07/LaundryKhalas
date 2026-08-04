"""Interactive, self-contained HTML replay report.

Renders each replayed conversation as a WhatsApp-style thread: the exact customer
message, the current agent reply, and the historical staff reply side-by-side,
with per-turn workflow chips, tool calls, cost, and evaluation badges. Filtering
(pass/fail, severity, service, divergence, human-intervention, model) is done
client-side over embedded JSON. No external assets — one openable file.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from ..core.config import ReplayConfig
from ..core.models import ReplayConversationResult
from ..core.pii import redact_text
from .writers import _conv_dict


def _summary(results: list[ReplayConversationResult], cfg: ReplayConfig) -> dict:
    total_turns = sum(len(r.turns) for r in results)
    grand = sum((t.usage.estimated_cost_usd for r in results for t in r.turns), 0.0)
    return {
        "run_id": results[0].replay_run_id if results else "",
        "model": cfg.model,
        "conversations": len(results),
        "turns": total_turns,
        "passed": sum(1 for r in results if r.overall_result == "PASS"),
        "critical": sum(r.critical_failures for r in results),
        "high": sum(r.high_failures for r in results),
        "medium": sum(r.medium_failures for r in results),
        "divergences": sum(r.divergence_count for r in results),
        "confirmed": sum(1 for r in results if r.order_confirmed),
        "cost": round(grand, 4),
        "redacted": cfg.redact_pii,
    }


def write_html_report(results: list[ReplayConversationResult], out: Path, cfg: ReplayConfig) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    convs = [_conv_dict(r, cfg) for r in results]
    summary = _summary(results, cfg)
    data_json = json.dumps({"summary": summary, "conversations": convs}, default=str)
    html_doc = _TEMPLATE.replace("/*__DATA__*/", "window.__REPLAY__ = " + data_json + ";")
    out.write_text(html_doc, encoding="utf-8")


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>LaundryKhalas — Historical Replay Report</title>
<style>
  :root{--ink:#0f1419;--ink2:#1b2530;--panel:#141b22;--line:#243040;--muted:#8aa0b3;
        --fg:#e7eef4;--orange:#ff7a1a;--in:#243b4a;--out:#1f4d3a;--hist:#3a2f1a;
        --crit:#ff4d4f;--high:#ff9800;--med:#ffd23f;--low:#7aa2c2;--pass:#3ecf8e;}
  *{box-sizing:border-box}
  body{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--ink);color:var(--fg)}
  header{padding:16px 22px;border-bottom:1px solid var(--line);background:var(--ink2);position:sticky;top:0;z-index:5}
  header h1{margin:0;font-size:17px;font-weight:600}
  header .sub{color:var(--muted);font-size:12px;margin-top:3px}
  .kpis{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
  .kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px;min-width:96px}
  .kpi b{display:block;font-size:18px}.kpi span{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
  .wrap{display:flex;height:calc(100vh - 132px)}
  .list{width:340px;border-right:1px solid var(--line);overflow-y:auto;background:var(--ink2)}
  .filters{padding:10px 12px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--ink2);z-index:2}
  .filters select,.filters input{width:100%;margin:4px 0;background:var(--panel);color:var(--fg);
        border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:12px}
  .citem{padding:10px 12px;border-bottom:1px solid var(--line);cursor:pointer}
  .citem:hover{background:var(--panel)}.citem.active{background:var(--panel);border-left:3px solid var(--orange)}
  .citem .cid{font-weight:600;font-size:13px}
  .citem .meta{color:var(--muted);font-size:11px;margin-top:2px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .thread{flex:1;overflow-y:auto;padding:18px 22px}
  .turn{margin-bottom:22px;border-bottom:1px dashed var(--line);padding-bottom:16px}
  .bubbles{display:flex;flex-direction:column;gap:8px}
  .b{max-width:76%;padding:8px 12px;border-radius:12px;white-space:pre-wrap;word-break:break-word}
  .b.cust{align-self:flex-start;background:var(--in)}
  .b.agent{align-self:flex-end;background:var(--out)}
  .b.hist{align-self:flex-end;background:var(--hist);opacity:.9;border:1px dashed #6b5a2a}
  .b .who{font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:2px}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
  .chip{font-size:11px;padding:2px 8px;border-radius:20px;background:var(--panel);border:1px solid var(--line);color:var(--muted)}
  .badge{font-size:11px;padding:2px 8px;border-radius:6px;font-weight:600;color:#0b0f14}
  .badge.CRITICAL{background:var(--crit);color:#fff}.badge.HIGH{background:var(--high)}
  .badge.MEDIUM{background:var(--med)}.badge.LOW{background:var(--low)}.badge.PASS{background:var(--pass)}
  .divg{color:var(--med);font-size:12px;margin-top:6px}
  .tools{font-size:12px;color:var(--muted);margin-top:6px}
  .empty{color:var(--muted);padding:40px;text-align:center}
  code{background:#0b1016;padding:1px 5px;border-radius:4px}
  .mono{font-family:ui-monospace,Menlo,Consolas,monospace}
</style></head>
<body>
<header>
  <h1>LaundryKhalas — Historical WhatsApp Replay <span id="runid" class="sub"></span></h1>
  <div class="sub" id="banner"></div>
  <div class="kpis" id="kpis"></div>
</header>
<div class="wrap">
  <div class="list">
    <div class="filters">
      <input id="q" placeholder="Search chat id / text…">
      <select id="fresult"><option value="">All results</option><option>PASS</option><option>WARN</option><option>FAIL</option><option>CRITICAL</option><option>ERROR</option></select>
      <select id="fsev"><option value="">Any severity</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select>
      <select id="fcat"><option value="">All categories</option></select>
      <select id="fflag">
        <option value="">Any</option>
        <option value="divergence">Has divergence</option>
        <option value="confirmed">Order confirmed</option>
        <option value="takeover">Human intervention</option>
        <option value="long">Long reply</option>
      </select>
    </div>
    <div id="clist"></div>
  </div>
  <div class="thread" id="thread"><div class="empty">Select a conversation.</div></div>
</div>
<script>
/*__DATA__*/
const D = window.__REPLAY__ || {summary:{},conversations:[]};
const esc = s => (s==null?'':(''+s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function kpi(v,l){return `<div class="kpi"><b>${v}</b><span>${l}</span></div>`}
function renderHead(){
  const s=D.summary;
  document.getElementById('runid').textContent = s.run_id||'';
  document.getElementById('banner').innerHTML =
    `Model <code>${esc(s.model)}</code> · ${s.conversations} conversations · ${s.turns} turns · `+
    (s.redacted?'PII redacted':'PII shown')+' · historical staff replies shown for comparison only (never fed to the agent)';
  document.getElementById('kpis').innerHTML =
    kpi(s.conversations,'chats')+kpi(s.turns,'turns')+kpi(s.passed,'passed')+
    kpi(s.critical,'critical')+kpi(s.high,'high')+kpi(s.medium,'medium')+
    kpi(s.divergences,'divergences')+kpi(s.confirmed,'confirmed')+kpi('$'+s.cost,'cost');
  const cats=[...new Set(D.conversations.map(c=>c.category))].sort();
  const sel=document.getElementById('fcat');
  cats.forEach(c=>{const o=document.createElement('option');o.value=c;o.textContent=c;sel.appendChild(o)});
}
function convMatches(c){
  const q=document.getElementById('q').value.toLowerCase();
  const fr=document.getElementById('fresult').value;
  const fsev=document.getElementById('fsev').value;
  const fcat=document.getElementById('fcat').value;
  const ff=document.getElementById('fflag').value;
  if(fr && c.overall_result!==fr) return false;
  if(fcat && c.category!==fcat) return false;
  if(fsev){const has=c.turns.some(t=>t.findings.some(f=>f.severity===fsev));if(!has)return false;}
  if(ff==='divergence' && c.divergence_count===0) return false;
  if(ff==='confirmed' && !c.order_confirmed) return false;
  if(ff==='takeover' && !c.turns.some(t=>t.workflow.human_intervention_status==='human_takeover')) return false;
  if(ff==='long' && !c.turns.some(t=>t.style.word_count>60)) return false;
  if(q){
    const hay=(c.source_chat_id+' '+c.turns.map(t=>t.customer_message+' '+t.agent_reply).join(' ')).toLowerCase();
    if(!hay.includes(q)) return false;
  }
  return true;
}
function renderList(){
  const box=document.getElementById('clist');box.innerHTML='';
  const shown=D.conversations.filter(convMatches);
  shown.forEach((c,i)=>{
    const div=document.createElement('div');div.className='citem';div.dataset.id=c.source_chat_id;
    const badge=`<span class="badge ${c.overall_result==='PASS'?'PASS':(c.critical_failures?'CRITICAL':(c.high_failures?'HIGH':'MEDIUM'))}">${c.overall_result}</span>`;
    div.innerHTML=`<div class="cid">${esc(c.source_chat_id)}</div>
      <div class="meta">${badge}<span class="chip">${esc(c.category)}</span>
      <span>${c.turns.length} turns</span>${c.order_confirmed?'<span class="chip">confirmed</span>':''}
      ${c.divergence_count?'<span class="chip">⤳ '+c.divergence_count+'</span>':''}</div>`;
    div.onclick=()=>{document.querySelectorAll('.citem').forEach(e=>e.classList.remove('active'));
      div.classList.add('active');renderThread(c);};
    box.appendChild(div);
  });
  if(!shown.length) box.innerHTML='<div class="empty">No conversations match.</div>';
}
function chip(label,val){return val?`<span class="chip">${esc(label)}: ${esc(val)}</span>`:''}
function renderThread(c){
  const t=document.getElementById('thread');
  let h=`<h2 style="margin:0 0 4px">${esc(c.source_chat_id)} <span class="chip">${esc(c.category)}</span></h2>`;
  h+=`<div class="tools" style="margin-bottom:14px">synthetic: <code>${esc(c.synthetic_customer_id)}</code> · final state: ${esc(c.final_order_state||'—')} · cost $${c.usage_total.estimated_cost_usd}</div>`;
  c.turns.forEach(tn=>{
    h+='<div class="turn"><div class="bubbles">';
    h+=`<div class="b cust"><div class="who">customer${tn.media_type?' · '+tn.media_type:''}</div>${esc(tn.customer_message)||'<i>(media)</i>'}</div>`;
    if(tn.agent_reply) h+=`<div class="b agent"><div class="who">current agent</div>${esc(tn.agent_reply)}</div>`;
    else h+=`<div class="b agent"><div class="who">current agent</div><i>(no text reply)</i></div>`;
    if(tn.historical_reply) h+=`<div class="b hist"><div class="who">historical staff (comparison only)</div>${esc(tn.historical_reply)}</div>`;
    h+='</div>';
    const w=tn.workflow;
    h+='<div class="chips">';
    h+=chip('service',w.resolved_service)+chip('state',w.order_state_after)+chip('total',w.final_total)
      +chip('discount',w.discount_amount)+chip('pickup',w.selected_pickup_slot)+chip('facility',w.facility_selection_result)
      +chip('confirm',w.confirmation_status)+chip('takeover',w.human_intervention_status==='human_takeover'?'yes':'')
      +chip('words',tn.style.word_count)+chip('cost','$'+(tn.usage.estimated_cost_usd||0).toFixed(4));
    h+='</div>';
    if(tn.tool_calls.length) h+=`<div class="tools">tools: ${tn.tool_calls.map(x=>esc(x.name)+(x.success?'':' ⚠')).join(', ')}</div>`;
    if(tn.findings.length) h+='<div class="chips">'+tn.findings.map(f=>`<span class="badge ${f.severity}" title="${esc(f.message)}">${esc(f.code)}</span>`).join('')+'</div>';
    if(tn.divergence) h+=`<div class="divg">⤳ divergence: ${esc(tn.divergence.type)} (agent asked: ${esc(tn.divergence.agent_requested_field)})</div>`;
    if(tn.error) h+=`<div class="divg">error: ${esc(tn.error)}</div>`;
    h+='</div>';
  });
  t.innerHTML=h;t.scrollTop=0;
}
['q','fresult','fsev','fcat','fflag'].forEach(id=>document.getElementById(id).addEventListener('input',renderList));
renderHead();renderList();
</script>
</body></html>"""
