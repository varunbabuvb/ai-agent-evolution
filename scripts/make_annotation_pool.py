"""Stratified sample of corpus_v1 -> pilot (15 shared) + 4 batches of 75. Usage: python scripts/make_annotation_pool.py data/interim/corpus_v1_clean.jsonl data/annotations/pool_v0.json (seed 42). Run on the CLEANED corpus (it carries the low_signal_release / llm_terms_found flags)."""
import json, random, re, sys, collections
src, out = sys.argv[1], sys.argv[2]
random.seed(42)
rows=[json.loads(l) for l in open(src)]
CUT="2026-09-30"
LLM=re.compile(r'\bLLMs?\b|language model|GPT|agentic|foundation model|tool[- ]use|function call|Claude|Gemini|\bMCP\b|copilot|chatbot',re.I)
def keep(r):
    m = r.get('metadata', {})
    if len(r['text'])<150 or not ("2017-01-01"<=r['publication_date']<=CUT): return False
    if r['source_type']=='release_notes' and (m.get('low_signal_release') or len(r['text'])<300): return False
    if r['source_type']=='paper' and r['publication_date']>='2023' and not m.get('llm_terms_found'): return False
    return True
ok=[r for r in rows if keep(r)]
HINT={
 'incident':r'incident|vulnerab|jailbreak|unexpected|misalign|attack|exploit|safety|failure',
 'multi':r'multi-agent|multiagent|agent-to-agent|\bA2A\b|collaborat|delegat|orchestrat|swarm',
 'adopt':r'deploy|adoption|million|enterprise|rollout|available to all|generally available',
 'infra':r'\bAPI\b|\bSDK\b|\bMCP\b|platform|infrastructure|plugin|integration',
 'auton':r'autonomous|long-horizon|agentic|computer use|browser|operator',
}
def hint(r):
    t=r['title']+' '+r['text'][:1500]
    return [k for k,p in HINT.items() if re.search(p,t,re.I)]
for r in ok: r['_h']=hint(r)
quota={2017:8,2018:8,2019:8,2020:8,2021:8,2022:16,2023:45,2024:60,2025:80,2026:82}
chosen=[]
for y,q in quota.items():
    pool=[r for r in ok if r['publication_date'].startswith(str(y))]
    random.shuffle(pool)
    if y<2023:
        pp=[r for r in pool if r['source_type']=='paper'][:2]
        pool=[r for r in pool if r['source_type']!='paper']+pp
    bytype=collections.defaultdict(list)
    for r in pool: bytype[r['source_type']].append(r)
    # proportional-with-floor by source type
    tot=len(pool); picks=[]
    for st,lst in bytype.items():
        n=max(1,round(q*len(lst)/tot)) if len(lst)>=1 else 0
        lst.sort(key=lambda r:-len(r['_h']))      # prefer rare-category hints
        top=lst[:max(1,n//3)]; rest=lst[max(1,n//3):]; random.shuffle(rest)
        picks+=top+rest[:n-len(top)]
    random.shuffle(picks)
    chosen+=picks[:q]
# fill any shortfall
ids={r['doc_id'] for r in chosen}
extra=[r for r in ok if r['doc_id'] not in ids]; random.shuffle(extra)
chosen+=extra[:315-len(chosen)]
chosen=chosen[:315]
random.shuffle(chosen)
# pilot: 15 shared, spread over years/types
chosen.sort(key=lambda r:(r['publication_date']))
pilot=[chosen[i] for i in range(7,315,21)][:15]
pid={r['doc_id'] for r in pilot}
rest=[r for r in chosen if r['doc_id'] not in pid]; random.shuffle(rest)
batches={a:rest[i*75:(i+1)*75] for i,a in enumerate(['VV','SH','TS','HA'])}
rem=rest[300:]  # 0 left expected
res={'pilot':pilot,**batches}
slim=lambda r:{k:r[k] for k in ['doc_id','title','publication_date','source','source_type','url']}|{'text_excerpt':re.sub(r'\s+',' ',r['text'])[:700],'hint':",".join(r['_h'])}
json.dump({k:[slim(r) for r in v] for k,v in res.items()},open(out,'w'),indent=1)
for k,v in res.items():
    print(k,len(v),collections.Counter(r['source_type'] for r in v).most_common(),collections.Counter(r['publication_date'][:4] for r in v).most_common(3))
print("hint coverage",collections.Counter(h for r in chosen for h in r['_h']))
