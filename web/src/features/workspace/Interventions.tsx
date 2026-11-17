import { useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { api } from '../../lib/api';
import type { Scope } from './types';

type Comparison = {asset_id: string; channel: string; unit: string; baseline_recent_mean: number | null; intervention_recent_mean: number | null; difference: number | null; trajectory: {observed_at: string; baseline: number | null; intervention: number | null}[]};
type Fleet = {asset_id: string; quality: string; missing_samples: number; latest_observed_at: string; trend_mechanisms: string[]}[];

export function Interventions({scope, disabled}: {scope: Scope | null; disabled: boolean}) {
  const [hour,setHour] = useState(48); const [factor,setFactor] = useState(0.8);const [kind,setKind] = useState('service');
  const [result,setResult] = useState<{comparison: Comparison[]; limitations: string[]; as_of: string} | null>(null);
  const [fleet,setFleet] = useState<Fleet | null>(null); const [index,setIndex] = useState(0); const [busy,setBusy] = useState(false); const [error,setError] = useState('');
  async function run(which: 'intervention' | 'fleet') {if(!scope)return;setBusy(true);setError('');try {
    if(which === 'intervention') {setResult(await api('/simulations/what-if',{scenario_id: scope.scenario_id,as_of: scope.as_of,...(kind === 'service'?{service_hour:hour}:{load_factor:factor})}));setIndex(0);}
    else setFleet((await api<{assets:Fleet}>(`/fleet/overview?scenario_id=${scope.scenario_id}&as_of=${encodeURIComponent(scope.as_of || '')}`)).assets);
  } catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  const chosen=result?.comparison[index];
  return <section><h3>SIMULATED intervention comparison</h3><p className="limit-note">Same seed and initial noise. Explicit toy response rules, without physical causal validity. Both trajectories stop at the selected replay cutoff.</p>{!scope && <p>Select an incident and asset in Context first.</p>}
    <fieldset disabled={disabled || busy || !scope}><label>Assumption<select value={kind} onChange={e => setKind(e.target.value)}><option value="service">Oil service at a specified hour</option><option value="load">Change modeled motor load/current</option></select></label>{kind==='service'?<label>Service hour<input type="number" min={0} max={96} value={hour} onChange={e => setHour(Number(e.target.value))}/></label>:<label>Load factor<input type="number" min={0.5} max={1.2} step={0.05} value={factor} onChange={e => setFactor(Number(e.target.value))}/></label>}<button className="primary" onClick={() => run('intervention')}>Run actual toy regeneration</button><button className="secondary" onClick={() => run('fleet')}>Compute fleet quality and trends</button></fieldset>
    {error && <p role="alert" className="error">{error}</p>}{busy && <p role="status">Computing from local observations…</p>}
    {result && <><p className="source-label">SIMULATED · cutoff {result.as_of}</p><label>Compared asset/channel<select value={index} onChange={e => setIndex(Number(e.target.value))}>{result.comparison.map((row,i) => <option key={`${row.asset_id}-${row.channel}`} value={i}>{row.asset_id}/{row.channel} ({row.unit})</option>)}</select></label>{chosen && <><p>Recent mean: {chosen.baseline_recent_mean?.toFixed(4) ?? 'missing'} → {chosen.intervention_recent_mean?.toFixed(4) ?? 'missing'} {chosen.unit}; difference {chosen.difference?.toFixed(4) ?? 'unavailable'}.</p><ResponsiveContainer width="100%" height={230}><LineChart data={chosen.trajectory}><XAxis dataKey="observed_at" tickFormatter={v=>String(v).slice(5,16)} tick={{fontSize:10}}/><YAxis domain={['auto','auto']} width={60}/><Tooltip/><Legend/><Line dataKey="baseline" stroke="#73867b" dot={false} connectNulls={false}/><Line dataKey="intervention" stroke="#287561" dot={false} connectNulls={false}/></LineChart></ResponsiveContainer></>}<ul>{result.limitations.map(text=><li key={text}>{text}</li>)}</ul></>}
    {fleet && <><h3>Actual fleet prefix indicators</h3><p className="muted">Quality and candidate trends, not failure probabilities.</p>{fleet.map(asset => <article className="evidence" key={asset.asset_id}><strong>{asset.asset_id}</strong><p>{asset.quality} · {asset.missing_samples} missing/flagged samples</p><p>Last observed: {asset.latest_observed_at || 'none available'}</p><p>Candidate trend rules: {asset.trend_mechanisms.join(', ') || 'none'}</p></article>)}</>}
  </section>;
}
