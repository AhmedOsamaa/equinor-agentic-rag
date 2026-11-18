"""Dashboard for generation pilots: percentages at the top, one expandable card per response, and your own judgments.

Run: uv run python eval/generation_dashboard.py [--port 8766] [--open]

Reads results/generation_<split>_<tag>.jsonl (written by eval/generation_run.py) and the chunk texts in data/chunks.jsonl.
Your verdicts are saved to results/generation_<split>_<tag>_judgments.json (one entry per question id), so closing the
browser loses nothing. Standard library only; binds 127.0.0.1; POSTs need the token that only this page knows.

Two kinds of numbers, never mixed:
  - mechanical: counted from the saved replies (did it parse, did the status match the question's behaviour, did a cited chunk
    contain a gold quote). They say nothing about whether an answer is right.
  - judged: only your verdicts. Shown with n judged out of n total, so a half-finished judging session is not read as a result.
"""

import json
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rag import config
from rag.evidence import contains_quote

TOKEN = secrets.token_urlsafe(16)
# The status a well-behaved model gives for each kind of question. unanswerable_near is "not in context": the document says
# something related but not the asked-for fact.
EXPECTED = {"answerable": "answered", "unanswerable_out": "not_in_context", "unanswerable_near": "not_in_context",
            "ambiguous": "ambiguous"}
VERDICTS = {"correct": {"yes", "partly", "no", "na"}, "faithful": {"yes", "partly", "no", "na"}}
_chunks: dict[str, str] = {}


def run_keys() -> list[str]:
    return sorted((p.stem for p in config.RESULTS_DIR.glob("generation_*.jsonl")), reverse=True)


def judgments_path(key: str):
    return config.RESULTS_DIR / f"{key}_judgments.json"


def load_run(key: str) -> dict:
    """All records of one run with the passages the model saw, plus the saved judgments."""
    if not _chunks:
        with open(config.CHUNKS_PATH, encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                _chunks[c["chunk_id"]] = c["text"]
    records = [json.loads(line) for line in (config.RESULTS_DIR / f"{key}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in records:
        cited = set(r["citations"] or [])
        r["expected_status"] = EXPECTED[r["behaviour"]]
        r["passages"] = [
            {"n": h["n"], "doc_id": h["doc_id"], "page": h["page"], "cited": h["n"] in cited,
             "has_gold": any(g["doc_id"] == h["doc_id"] and contains_quote(_chunks[h["chunk_id"]], g["evidence_quote"]) for g in r["gold"]),
             "text": _chunks[h["chunk_id"]]}
            for h in r["retrieved"]
        ]
        del r["retrieved"]
    path = judgments_path(key)
    claude = config.RESULTS_DIR / f"{key}_claude_judgments.json"   # read-only: written by Claude, never edited here
    return {"key": key, "records": records, "judgments": json.loads(path.read_text(encoding="utf-8")) if path.exists() else {},
            "claude": json.loads(claude.read_text(encoding="utf-8")) if claude.exists() else {}}


def save_judgment(key: str, qid: str, body: dict) -> None:
    if key not in run_keys():
        raise ValueError("unknown run")
    entry = {k: body.get(k) for k in VERDICTS}
    if any(v not in VERDICTS[k] and v is not None for k, v in entry.items()):
        raise ValueError("bad verdict")
    entry["note"] = str(body.get("note", ""))[:2000]
    path = judgments_path(key)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[qid] = entry
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


PAGE = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Generation pilot</title>
<style>
body{font:14px/1.45 system-ui,sans-serif;margin:0;background:#f6f7f9;color:#1b1f24}
header{background:#fff;border-bottom:1px solid #d8dde3;padding:12px 24px;display:flex;gap:16px;align-items:center}
main{max-width:1150px;margin:0 auto;padding:16px 24px 60px}
h2{font-size:15px;margin:22px 0 6px}
table{border-collapse:collapse;background:#fff;border:1px solid #d8dde3}
td,th{padding:5px 11px;border-bottom:1px solid #eceff2;text-align:left;font-size:13px}
th{background:#f0f2f5;font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.note{color:#5b6670;font-size:12px;margin:4px 0}
.row{background:#fff;border:1px solid #d8dde3;border-radius:6px;margin:6px 0}
.row>summary{cursor:pointer;padding:8px 12px;display:flex;gap:10px;align-items:baseline}
.row[open]>summary{border-bottom:1px solid #eceff2}
.body{padding:10px 14px}
.tag{font-size:11px;padding:1px 7px;border-radius:9px;background:#e8ebef;white-space:nowrap}
.ok{background:#d9f0de}.bad{background:#f7d9d6}.mid{background:#faecc8}
.q{flex:1}
.lbl{font-weight:600;font-size:12px;color:#5b6670;margin-top:8px}
.box{white-space:pre-wrap;background:#f6f7f9;border:1px solid #e3e7eb;border-radius:4px;padding:6px 9px}
.pass{border:1px solid #e3e7eb;border-radius:4px;margin:4px 0}
.pass>summary{padding:3px 8px;cursor:pointer;font-size:12px}
.pass.cited{border-color:#3b7dd8}.pass.gold>summary{background:#e6f4ea}
.pass pre{margin:0;padding:6px 9px;white-space:pre-wrap;font:12px/1.4 ui-monospace,monospace;max-height:260px;overflow:auto}
.cols{display:flex;gap:14px;margin-top:8px}.col{flex:1;min-width:0;border:1px solid #e3e7eb;border-radius:6px;padding:4px 10px 8px}
.claude{margin-top:8px;padding:5px 9px;background:#eef3fb;border:1px dashed #9db6dd;border-radius:4px;font-size:12px}
.judge button{margin-right:4px;padding:3px 9px;border:1px solid #aab3bd;background:#fff;border-radius:4px;cursor:pointer}
.judge button.on{background:#1b4f9c;color:#fff;border-color:#1b4f9c}
select,input[type=text],textarea{font:inherit}
textarea{width:100%;height:46px}
</style>
<header><b>Generation pilot</b> <select id="run"></select> <span id="model" class="note"></span>
<span class="note">compare with</span> <select id="cmp"><option value="">(none)</option></select>
<label><input type="checkbox" id="f_diff"> review set: status differs from compare run + all non-answerable/ambiguous</label>
<label><input type="checkbox" id="f_mis"> status not as expected</label>
<label><input type="checkbox" id="f_unj"> not judged yet</label>
<select id="f_beh"><option value="">all behaviours</option></select></header>
<main><div id="summary"></div><h2>Responses</h2><div id="list"></div></main>
<script>
const TOKEN="__TOKEN__";
let D=null, J={}, C={}, CD=null, CJ={};   // C: records of the compare run by id; CD its data; CJ its judgments
// Review set: where the compare run's status differs, plus every question that is not a plain answerable one.
const inReviewSet=r=>r.behaviour!=="answerable"||(C[r.id]&&C[r.id].status!==r.status);
const $=id=>document.getElementById(id);
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!==undefined)e.textContent=x;return e};
const pct=(a,b)=>b?(100*a/b).toFixed(0)+"% ("+a+"/"+b+")":"n/a (0)";
async function init(){
  const keys=await (await fetch("/api/runs")).json();
  keys.forEach(k=>{const o=el("option","",k);o.value=k;$("run").appendChild(o);const o2=el("option","",k);o2.value=k;$("cmp").appendChild(o2)});
  $("run").onchange=load; ["f_mis","f_unj","f_beh","f_diff"].forEach(i=>$(i).onchange=renderList);
  $("cmp").onchange=async()=>{C={};CD=null;CJ={}; if($("cmp").value){CD=await (await fetch("/api/data?key="+encodeURIComponent($("cmp").value))).json(); CJ=CD.judgments; CD.records.forEach(r=>C[r.id]=r)} render()};
  if(keys.length) load();
}
async function load(){
  D=await (await fetch("/api/data?key="+encodeURIComponent($("run").value))).json(); J=D.judgments;
  $("model").textContent=D.records.length?D.records[0].model:"";
  const behs=[...new Set(D.records.map(r=>r.behaviour))]; $("f_beh").innerHTML='<option value="">all behaviours</option>';
  behs.forEach(b=>{const o=el("option","",b);o.value=b;$("f_beh").appendChild(o)});
  render();
}
function render(){renderSummary();renderList()}
function renderSummary(){
  const R=D.records, S=$("summary"); S.innerHTML="";
  renderCompare(S);
  const parsed=R.filter(r=>r.status).length;
  S.appendChild(el("div","note","Replies that parsed as valid JSON: "+pct(parsed,R.length)+"  |  mean prompt tokens "+Math.round(R.reduce((a,r)=>a+r.prompt_tokens,0)/R.length)+", mean latency "+(R.reduce((a,r)=>a+r.latency_s,0)/R.length).toFixed(1)+" s"));
  S.appendChild(el("h2","","1. What the model did, by question behaviour (mechanical, no judgment of the content)"));
  const t=el("table"); t.innerHTML="<tr><th>question behaviour</th><th>n</th><th>answered</th><th>not_in_context</th><th>ambiguous</th><th>unparsed</th><th>status as expected</th></tr>";
  const groups=[...new Set(R.map(r=>r.behaviour))];
  groups.forEach(g=>{const rs=R.filter(r=>r.behaviour==g); const c=s=>rs.filter(r=>r.status===s).length;
    const tr=el("tr"); [g,rs.length,pct(c("answered"),rs.length),pct(c("not_in_context"),rs.length),pct(c("ambiguous"),rs.length),c(null),pct(rs.filter(r=>r.status===r.expected_status).length,rs.length)].forEach((v,i)=>tr.appendChild(el("td",i?"n":"",v))); t.appendChild(tr)});
  S.appendChild(t);
  S.appendChild(el("div","note","Expected status: answerable = answered; unanswerable_out and unanswerable_near = not_in_context; ambiguous = ambiguous. 'As expected' is not 'correct': an answered reply can still carry the wrong number."));
  S.appendChild(el("h2","","2. Retrieval ceiling and citations (answerable questions with gold quotes)"));
  const A=R.filter(r=>r.behaviour=="answerable"&&r.retrieved_gold!==null);
  const ans=A.filter(r=>r.status==="answered");
  const t2=el("table"); t2.innerHTML="<tr><th>measure</th><th>value</th></tr>";
  [["a chunk with the gold quote was in the top 10 (retrieval ceiling)",pct(A.filter(r=>r.retrieved_gold).length,A.length)],
   ["...and the model refused or called it ambiguous anyway (over-refusal)",pct(A.filter(r=>r.retrieved_gold&&r.status!=="answered").length,A.filter(r=>r.retrieved_gold).length)],
   ["answered replies whose citations include a gold-quote chunk",pct(ans.filter(r=>r.cited_gold).length,ans.length)],
   ["answered replies citing a passage number that does not exist",pct(ans.filter(r=>r.bad_citation_numbers.length).length,ans.length)]]
  .forEach(([a,b])=>{const tr=el("tr");tr.appendChild(el("td","",a));tr.appendChild(el("td","n",b));t2.appendChild(tr)});
  S.appendChild(t2);
  S.appendChild(el("h2","","3. Your judgments (only what you have judged so far)"));
  const judged=R.filter(r=>J[r.id]); const t3=el("table"); t3.innerHTML="<tr><th>question</th><th>n judged / total</th><th>yes</th><th>partly</th><th>no</th></tr>";
  [["correct","Is the answer correct against the reference?"],["faithful","Is every claim supported by the passages shown?"]].forEach(([k,label])=>{
    const rs=judged.filter(r=>J[r.id][k]&&J[r.id][k]!=="na"); const c=v=>rs.filter(r=>J[r.id][k]===v).length;
    const tr=el("tr"); [label,rs.length+" / "+R.length,pct(c("yes"),rs.length),pct(c("partly"),rs.length),pct(c("no"),rs.length)].forEach((v,i)=>tr.appendChild(el("td",i?"n":"",v))); t3.appendChild(tr)});
  S.appendChild(t3);
  S.appendChild(el("div","note","Percentages are of the judged answers only. Judge in id order or all of them before quoting a number; n is always shown. 'na' (not applicable) is left out."));
}
const hasCmp=()=>!!CD&&CD.key!==D.key;
const store=key=>key===D.key?J:CJ;
const claudeOf=key=>(key===D.key?D.claude:(CD&&CD.claude))||{};
const metrics=(R,key)=>{
  const ansq=R.filter(r=>r.behaviour==="answerable"), A=ansq.filter(r=>r.retrieved_gold!==null), ans=A.filter(r=>r.status==="answered");
  const NA=R.filter(r=>r.behaviour!=="answerable"), n=(rs,st)=>rs.filter(r=>r.status===st).length;
  const sel=f=>{const rs=R.filter(r=>store(key)[r.id]&&store(key)[r.id][f]&&store(key)[r.id][f]!=="na");return [rs,v=>rs.filter(r=>store(key)[r.id][f]===v).length]};
  const [cr,cc]=sel("correct"), [fr,fc]=sel("faithful");
  return [
   ["model",R[0].model],
   ["replies that parsed as valid JSON",pct(R.filter(r=>r.status).length,R.length)],
   ["answerable questions answered",pct(n(ansq,"answered"),ansq.length)],
   ["answerable called ambiguous",pct(n(ansq,"ambiguous"),ansq.length)],
   ["answerable called not_in_context",pct(n(ansq,"not_in_context"),ansq.length)],
   ["over-refusal (gold retrieved, not answered)",pct(A.filter(r=>r.retrieved_gold&&r.status!=="answered").length,A.filter(r=>r.retrieved_gold).length)],
   ["answered replies citing a gold-quote chunk",pct(ans.filter(r=>r.cited_gold).length,ans.length)],
   ["non-answerable/ambiguous: status as expected",pct(NA.filter(r=>r.status===r.expected_status).length,NA.length)],
   ["mean latency (s)",(R.reduce((a,r)=>a+r.latency_s,0)/R.length).toFixed(1)],
   ["YOUR judgment: correct = yes",pct(cc("yes"),cr.length)+"  of "+cr.length+" judged"],
   ["YOUR judgment: correct = partly / no",cc("partly")+" / "+cc("no")],
   ["YOUR judgment: faithful = yes",pct(fc("yes"),fr.length)+"  of "+fr.length+" judged"],
   ...claudeRows(R,key)];
};
// Claude's own read of every answer (an LLM-judge verdict, not a human judgment; Claude also wrote round 3 and 30 rewrites).
function claudeRows(R,key){
  const cj=claudeOf(key), rs=R.filter(r=>cj[r.id]); if(!rs.length) return [];
  const c=(f,v)=>rs.filter(r=>cj[r.id][f]===v).length;
  return [["CLAUDE check: correct = yes",pct(c("correct","yes"),rs.length)+"  of "+rs.length+" read"],
          ["CLAUDE check: correct = partly / no",c("correct","partly")+" / "+c("correct","no")],
          ["CLAUDE check: faithful = yes",pct(c("faithful","yes"),rs.length)],
          ["CLAUDE check: faithful = partly / no",c("faithful","partly")+" / "+c("faithful","no")]];
}
function renderCompare(S){
  if(!hasCmp()) return;
  S.appendChild(el("h2","","Side by side: "+D.key+"  vs  "+CD.key));
  const a=metrics(D.records,D.key), b=metrics(CD.records,CD.key), t=el("table"); t.innerHTML="<tr><th>measure (same questions, same prompt, same retrieval)</th><th>"+D.key+"</th><th>"+CD.key+"</th></tr>";
  a.forEach(([l,v],i)=>{const tr=el("tr"); tr.appendChild(el("td","",l)); tr.appendChild(el("td","n",v)); tr.appendChild(el("td","n",b[i][1])); t.appendChild(tr)});
  S.appendChild(t);
  S.appendChild(el("div","note","The judged rows count only what you have judged for each run, with n shown. Compare them only when both runs were judged on the same set of questions. Mechanical rows say nothing about whether an answer is right."));
}
function btns(qid,field,key){
  const box=el("span","judge"); const cur=(store(key)[qid]||{})[field];
  [["yes","yes"],["partly","partly"],["no","no"],["na","n/a"]].forEach(([v,label])=>{
    const b=el("button",cur===v?"on":"",label); b.onclick=()=>{save(key,qid,field,cur===v?null:v)}; box.appendChild(b)}); return box}
async function save(key,qid,field,val,note){
  const st=store(key), e=Object.assign({correct:null,faithful:null,note:""},st[qid]||{}); if(field) e[field]=val; if(note!==undefined) e.note=note;
  st[qid]=e;
  await fetch("/api/judge",{method:"POST",headers:{"X-Token":TOKEN,"Content-Type":"application/json"},body:JSON.stringify(Object.assign({key:key,id:qid},e))});
  renderSummary(); const open=new Set([...document.querySelectorAll(".row[open]")].map(d=>d.dataset.id)); renderList(open);
}
// One model's answer for one question: its status, answer, citations, mechanical notes and the judgment buttons.
function answerBlock(r,key){
  const c=el("div","col"), okc=r.status===r.expected_status?"ok":"bad";
  const h=el("div","lbl",r.model+"  ("+key+")  "); h.appendChild(el("span","tag "+okc,(r.status||"UNPARSED")+(okc=="ok"?"":" (expected "+r.expected_status+")"))); c.appendChild(h);
  c.appendChild(el("div","box",r.answer===null?"RAW REPLY: "+r.raw_reply:r.answer));
  c.appendChild(el("div","note","cites "+JSON.stringify(r.citations)+" | cited chunk has gold: "+r.cited_gold+" | tokens "+r.prompt_tokens+"/"+r.completion_tokens+" | "+r.latency_s+" s"));
  const jb=el("div","judge"); jb.appendChild(document.createTextNode("Correct: ")); jb.appendChild(btns(r.id,"correct",key));
  jb.appendChild(document.createTextNode("  Faithful: ")); jb.appendChild(btns(r.id,"faithful",key));
  const ta=el("textarea"); ta.placeholder="note (saved when you click away)"; ta.value=(store(key)[r.id]||{}).note||""; ta.onchange=()=>save(key,r.id,null,null,ta.value);
  jb.appendChild(ta); c.appendChild(jb);
  const cl=claudeOf(key)[r.id];
  if(cl){const cb=el("div","claude"); cb.appendChild(el("div","lbl","Claude's check (LLM opinion, not your judgment): correct = "+cl.correct+", faithful = "+cl.faithful)); cb.appendChild(el("div","",cl.note)); c.appendChild(cb)}
  return c}
const claudeTag=(key,id)=>{const j=claudeOf(key)[id]; return j?("claude c:"+j.correct+" f:"+j.faithful):""};
const judgedTag=(key,id)=>{const j=store(key)[id]; return j?("c:"+(j.correct||"-")+" f:"+(j.faithful||"-")):"not judged"};
function renderList(open){
  open=open instanceof Set?open:new Set(); const L=$("list"); L.innerHTML="";
  const cmpOn=hasCmp();
  if($("f_diff").checked&&!cmpOn) L.appendChild(el("div","note","Choose a compare run (a different one from the main run) first."));
  D.records.filter(r=>(!$("f_diff").checked||(cmpOn&&inReviewSet(r)))&&(!$("f_mis").checked||r.status!==r.expected_status)&&(!$("f_unj").checked||!J[r.id]||(cmpOn&&!CJ[r.id]))&&(!$("f_beh").value||r.behaviour===$("f_beh").value)).forEach(r=>{
    const o=cmpOn?C[r.id]:null;
    const d=el("details","row"); d.dataset.id=r.id; if(open.has(r.id)) d.open=true;
    const s=el("summary"); const okc=r.status===r.expected_status?"ok":"bad";
    s.appendChild(el("span","tag",r.id)); s.appendChild(el("span","tag",r.behaviour));
    s.appendChild(el("span","tag "+okc,(r.status||"UNPARSED")+(okc=="ok"?"":"  (expected "+r.expected_status+")")));
    if(o) s.appendChild(el("span","tag"+(o.status===r.status?"":" mid"),"vs "+(o.status||"UNPARSED")));
    s.appendChild(el("span","tag "+(J[r.id]?"mid":""),judgedTag(D.key,r.id))); if(o) s.appendChild(el("span","tag "+(CJ[r.id]?"mid":""),judgedTag(CD.key,r.id)));
    if(claudeOf(D.key)[r.id]) s.appendChild(el("span","tag",claudeTag(D.key,r.id))); if(o&&claudeOf(CD.key)[r.id]) s.appendChild(el("span","tag",claudeTag(CD.key,r.id)));
    s.appendChild(el("span","q",r.question)); d.appendChild(s);
    const b=el("div","body");
    const add=(l,t)=>{b.appendChild(el("div","lbl",l));b.appendChild(el("div","box",t))};
    add("Reference answer",r.reference_answer);
    add("Gold quotes",r.gold.length?r.gold.map(g=>"["+g.doc_id+" p."+g.page+"] "+g.evidence_quote).join("\\n"):"(none)");
    const cols=el("div","cols"); cols.appendChild(answerBlock(r,D.key)); if(o) cols.appendChild(answerBlock(o,CD.key)); b.appendChild(cols);
    b.appendChild(el("div","lbl","Passages both models saw (identical retrieval). Blue border = cited; green = holds a gold quote"));
    r.passages.forEach(p=>{
      const byA=p.cited, byB=!!(o&&(o.citations||[]).includes(p.n));
      const pd=el("details","pass"+((byA||byB)?" cited":"")+(p.has_gold?" gold":""));
      pd.appendChild(el("summary","","["+p.n+"] "+p.doc_id+", page "+p.page+(byA?"  - cited by "+r.model:"")+(byB?"  - cited by "+o.model:"")+(p.has_gold?"  - gold quote":"")));
      pd.appendChild(el("pre","",p.text)); b.appendChild(pd)});
    d.appendChild(b); L.appendChild(d)});
}
init();
</script></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "").split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        url = urlparse(self.path)
        if not self._host_ok():
            return self._send(403, b"{}")
        if url.path == "/":
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN).encode("utf-8"), "text/html")
        if url.path == "/api/runs":
            return self._send(200, json.dumps(run_keys()).encode("utf-8"))
        if url.path == "/api/data":
            key = parse_qs(url.query).get("key", [""])[0]
            if key not in run_keys():
                return self._send(404, b"{}")
            return self._send(200, json.dumps(load_run(key), ensure_ascii=False).encode("utf-8"))
        self._send(404, b"{}")

    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Token") != TOKEN or self.path != "/api/judge":
            return self._send(403, b"{}")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            save_judgment(body["key"], body["id"], body)
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
        self._send(200, b"{}")

    def log_message(self, *args):
        pass


def option(name: str, default: str) -> str:
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main() -> None:
    port = int(option("--port", "8766"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"generation dashboard at {url}  (Ctrl+C to stop); runs: {run_keys()}")
    if "--open" in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
