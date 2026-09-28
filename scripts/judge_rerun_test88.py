"""Re-judge test-88 production cells with bidirectional or v2-min prompt.

Usage:
  python scripts/judge_rerun_test88.py --mode bi    # bidirectional
  python scripts/judge_rerun_test88.py --mode v2min # single-direction v2-min

Output:
  data/judged/judge_scores_{bi,v2min}_glm5.parquet

Resumable: skips cells already in the output parquet on re-run.
"""

import argparse, json, os, re, sys, time, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

API_KEY = os.environ['DEEPINFRA_API_KEY']
URL = 'https://api.deepinfra.com/v1/openai/chat/completions'
MODEL = 'zai-org/GLM-5'
SYSTEM = ('You are scoring metadata extractions from ML dataset papers '
          'against a human-validated reference. Output JSON only: '
          '{"score": 1, 2, or 3, "reason": "one short sentence"}')


def v1_user(field, ref, cand):
    return f"""Field: {field}
Reference (human-validated): {ref}
Candidate (model output): {cand}

Rubric -- rate the candidate's similarity to the reference. The
reference is the authoritative answer for this paper-field cell.

1 = Correct. The candidate conveys the same meaning as the reference,
    capturing all or nearly all of the same content. Stylistic
    differences and minor omissions are acceptable.
2 = Partially correct. The candidate covers the topic and shares
    some content with the reference, but misses or distorts
    substantial parts of the meaning.
3 = Not correct. The candidate's meaning differs substantially from
    the reference, shares little content with it, contradicts it,
    or contains hallucinated information not supported by the
    reference.

Special case: if the reference is empty / NULL / "[NULL ...]" (paper
does not document this field), score 1 if the candidate is also
empty/null; score 3 if the candidate provides content (hallucination).

Return JSON only."""


def v2min_user(field, ref, cand):
    return f"""Field: {field}
Reference (human-validated): {ref}
Candidate (model output): {cand}

Rubric -- rate whether the candidate captures the same factual claim
as the reference. The reference is the authoritative answer for this
paper-field cell, but it is one valid phrasing among many. Phrasing
differences should not lower the score; only differences in factual
content should.

1 = Correct. The candidate captures the essential factual content of
    the reference. The following are EXPLICITLY ACCEPTABLE and should
    NOT lower the score:
      - Paraphrasing, rewording, or restructuring of the same facts
      - Additional accurate detail beyond what the reference contains,
        provided the reference's specific items are still preserved
      - Minor omissions of non-essential information
      - Different level of granularity (compressed vs. expanded)
      - Different ordering of items in a list
    Mark 1 whenever the candidate covers the central factual claim of
    the reference, regardless of phrasing or extra content.

2 = Partially correct. The candidate covers the topic but is missing
    the central factual claim of the reference, OR distorts a key
    fact, OR mixes correct content with clearly unrelated content.

3 = Not correct. The candidate's meaning differs substantially from
    the reference, contradicts it, or describes a different topic
    entirely.

Special case: if the reference is empty / NULL / "[NULL ...]" (paper
does not document this field), score 1 if the candidate is also
empty/null; score 3 if the candidate provides content (hallucination).
The reference is authoritative on whether the paper documents this
field.

Return JSON only."""


def call_judge(builder, field, ref, cand, retries=3):
    body = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user',   'content': builder(field, ref, cand)},
        ],
        'temperature': 0.0,
        'max_completion_tokens': 4000,
        'response_format': {'type': 'json_object'},
    }
    req_data = json.dumps(body).encode()
    headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(URL, data=req_data, headers=headers)
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            msg_obj = resp['choices'][0]['message']
            msg = msg_obj.get('content') or ''
            if not msg.strip() and msg_obj.get('reasoning_content'):
                msg = msg_obj['reasoning_content']
            if msg.strip().startswith('```'):
                msg = re.sub(r'^```(?:json)?\s*|\s*```$', '', msg.strip(), flags=re.S)
            if '</think>' in msg:
                msg = msg.split('</think>', 1)[-1]
            m = re.search(r'\{[^{}]*"score"[^{}]*\}', msg, re.S)
            if not m:
                last_err = f'no JSON in response: {msg[:100]}'
                time.sleep(2)
                continue
            parsed = json.loads(m.group(0))
            usage = resp.get('usage', {})
            return {
                'score': int(parsed.get('score', 0)),
                'reason': parsed.get('reason', ''),
                'input_tokens': usage.get('prompt_tokens', 0),
                'output_tokens': usage.get('completion_tokens', 0),
            }
        except Exception as e:
            last_err = str(e)[:200]
            time.sleep(min(2 ** attempt, 10))
    return {'score': None, 'reason': f'ERROR: {last_err}', 'input_tokens': 0, 'output_tokens': 0}


# ── Strategy directories (reuse production mapping) ──
sys.path.insert(0, str(ROOT))
from evaluation.score_against_gold import STRATEGY_DIRS, DEFAULT_GOLD_METHODS

GOLD = pd.read_parquet(ROOT / 'data/annotations/gold.parquet')
GOLD = GOLD[GOLD['gold_method'].isin(DEFAULT_GOLD_METHODS) & GOLD['gold_value'].notna()]
TEST_PAPERS = frozenset(json.loads((ROOT / 'data/agentic/dev_test_split.json').read_text())['test'])


def get_candidate(system_id, paper_id, field_id):
    sdir = STRATEGY_DIRS.get(system_id)
    if sdir is None or not sdir.exists():
        return None
    p = sdir / f'{paper_id}.json'
    if not p.exists():
        return None
    try:
        d = json.load(open(p))
        ext = d.get('extraction', d) if isinstance(d, dict) else {}
    except Exception:
        return None
    short = field_id.split(':')[-1] if ':' in field_id else field_id
    return ext.get(field_id, ext.get(short))


def process_cell_bi(cell):
    field, gold, cand = cell['field_id'], cell['gold_value'][:8000], cell['candidate'][:8000]
    fwd = call_judge(v1_user, field, gold, cand)
    rev = call_judge(v1_user, field, cand, gold)
    s_fwd, s_rev = fwd['score'], rev['score']
    if s_fwd is None or s_rev is None:
        bi_score = None
    elif s_fwd == 1:
        bi_score = 1
    else:
        bi_score = max(s_fwd, s_rev)
    return {**cell,
            'fwd_score': s_fwd, 'fwd_reason': fwd['reason'],
            'rev_score': s_rev, 'rev_reason': rev['reason'],
            'bi_score': bi_score,
            'input_tokens': fwd['input_tokens'] + rev['input_tokens'],
            'output_tokens': fwd['output_tokens'] + rev['output_tokens']}


def process_cell_v2min(cell):
    r = call_judge(v2min_user, cell['field_id'], cell['gold_value'][:8000], cell['candidate'][:8000])
    return {**cell, 'score': r['score'], 'reason': r['reason'],
            'input_tokens': r['input_tokens'], 'output_tokens': r['output_tokens']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['bi', 'v2min'], required=True)
    ap.add_argument('--concurrency', type=int, default=30)
    ap.add_argument('--limit', type=int, default=None)
    args = ap.parse_args()

    out_path = ROOT / f'data/judged/judge_scores_{args.mode}_glm5.parquet'
    print(f'[start] mode={args.mode}  out={out_path}', flush=True)

    # Load production GLM-5 cells (gives us the (system, paper, field) triples + scores)
    prod = pd.read_parquet(ROOT / 'data/judged/judge_scores_glm_5.parquet')
    prod = prod[prod.paper_id.isin(TEST_PAPERS)].copy()
    print(f'[plan] test-88 cells from production: {len(prod)}', flush=True)

    # Resume support: skip already-done cells
    done = set()
    if out_path.exists():
        prev = pd.read_parquet(out_path)
        done = set(zip(prev.paper_id, prev.field_id, prev.system_id))
        print(f'[resume] {len(done)} cells already done, skipping', flush=True)

    # Build task list
    gold_lookup = {(r['paper_id'], r['field_id']): r['gold_value']
                   for _, r in GOLD.iterrows()}
    tasks = []
    skipped = 0
    for _, r in prod.iterrows():
        key = (r['paper_id'], r['field_id'], r['system_id'])
        if key in done:
            continue
        gold = gold_lookup.get((r['paper_id'], r['field_id']))
        if gold is None:
            skipped += 1
            continue
        cand = get_candidate(r['system_id'], r['paper_id'], r['field_id'])
        if cand is None or not str(cand).strip():
            skipped += 1
            continue
        tasks.append({
            'paper_id': r['paper_id'], 'field_id': r['field_id'],
            'system_id': r['system_id'], 'gold_value': str(gold),
            'candidate': str(cand), 'v1_score': r['score']
        })
    if args.limit:
        tasks = tasks[:args.limit]
    print(f'[plan] tasks to run: {len(tasks)}  (skipped: {skipped})', flush=True)

    # Process with concurrency
    proc_fn = process_cell_bi if args.mode == 'bi' else process_cell_v2min
    n_calls = 2 if args.mode == 'bi' else 1
    results = []
    t0 = time.time()
    save_every = 500
    last_save = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(proc_fn, t): t for t in tasks}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                results.append(fut.result())
            except Exception as e:
                t = futures[fut]
                print(f'  [err] {t["paper_id"]}/{t["field_id"]}/{t["system_id"]}: {e}', flush=True)
            if i % 100 == 0 or i == len(tasks):
                elapsed = time.time() - t0
                rate = i / elapsed
                eta_sec = (len(tasks) - i) / rate if rate > 0 else 0
                in_sum = sum(r.get('input_tokens', 0) for r in results)
                out_sum = sum(r.get('output_tokens', 0) for r in results)
                cost = (in_sum * 0.40 + out_sum * 1.30) / 1e6
                print(f'  [{i:>5d}/{len(tasks)}] '
                      f'rate={rate:.1f}/s  elapsed={elapsed/60:.1f}min  '
                      f'eta={eta_sec/60:.1f}min  '
                      f'tokens_in={in_sum:,} tokens_out={out_sum:,}  '
                      f'cost=${cost:.2f}', flush=True)
            # Periodic save
            if len(results) - last_save >= save_every:
                df_partial = pd.DataFrame(results)
                if out_path.exists():
                    prev = pd.read_parquet(out_path)
                    df_partial = pd.concat([prev, df_partial], ignore_index=True)
                df_partial.to_parquet(out_path)
                last_save = len(results)

    # Final save
    df = pd.DataFrame(results)
    if out_path.exists() and len(done) > 0:
        prev = pd.read_parquet(out_path)
        df = pd.concat([prev, df], ignore_index=True).drop_duplicates(
            subset=['paper_id', 'field_id', 'system_id'], keep='last'
        )
    df.to_parquet(out_path)
    final_in = df.input_tokens.sum() if 'input_tokens' in df.columns else 0
    final_out = df.output_tokens.sum() if 'output_tokens' in df.columns else 0
    final_cost = (final_in * 0.40 + final_out * 1.30) / 1e6
    print(f'\n[done] mode={args.mode}  saved={len(df)} cells  '
          f'cost=${final_cost:.2f}  '
          f'time={(time.time()-t0)/60:.1f}min', flush=True)


if __name__ == '__main__':
    main()
