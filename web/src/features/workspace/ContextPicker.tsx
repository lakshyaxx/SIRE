import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import type { Scope, Scenario } from './types';

export function ContextPicker({value, onChange, disabled = false}: {value: Scope | null; onChange: (scope: Scope | null) => void; disabled?: boolean}) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [assets, setAssets] = useState<{id: string}[]>([]);
  const [error, setError] = useState('');
  function load() { api<{scenarios: Scenario[]}>('/scenarios').then(result => {setScenarios(result.scenarios);setError('');}).catch(e => setError(e.message)); }
  useEffect(load, []);
  useEffect(() => {if (!value) {setAssets([]);return;} let current = true; api<{assets: {id: string}[]}>(`/scenarios/${value.scenario_id}/assets`).then(result => {if (current) setAssets(result.assets);}).catch(e => {if (current) setError(e.message);});return () => {current = false;};}, [value?.scenario_id]);
  const scenario = scenarios.find(row => row.id === value?.scenario_id);
  const maxHour = scenario ? (Date.parse(scenario.ends_at) - Date.parse(scenario.starts_at)) / 3600000 : 0;
  const hour = scenario ? (Date.parse(value?.as_of || scenario.reference_at) - Date.parse(scenario.starts_at)) / 3600000 : 0;
  function cutoff(hour: number) {if (value && scenario) onChange({...value, case_id: null, as_of: new Date(Date.parse(scenario.starts_at) + hour * 3600000).toISOString()});}
  return <section className="scope-picker"><h3>Investigation context</h3><p className="muted">Select a simulated incident to enable historical tools. NASA and uploaded physical evidence retain separate provenance.</p>
    {error && <p role="alert" className="error">{error} <button onClick={load}>Retry</button></p>}
    <label>SIMULATED incident<select aria-label="Investigation incident" disabled={disabled} value={value?.scenario_id || ''} onChange={e => {const selected = scenarios.find(s => s.id === e.target.value);onChange(selected ? {scenario_id: selected.id, asset_id: selected.asset_id, as_of: selected.reference_at} : null);}}><option value="">No facility context</option>{scenarios.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
    {value && <><label>Asset<select aria-label="Investigation asset" disabled={disabled} value={value.asset_id} onChange={e => onChange({...value, asset_id: e.target.value, case_id: null})}>{assets.map(a => <option key={a.id}>{a.id}</option>)}</select></label><label>Historical information cutoff<input aria-label="Chat replay cutoff" type="range" disabled={disabled} min={0} max={maxHour} step={1} value={hour} onChange={e => cutoff(Number(e.target.value))}/></label><time className="cutoff-label">{value.as_of}</time><div className="replay-actions">{[48,24,12,0].map(before => <button className="secondary" type="button" disabled={disabled} key={before} onClick={() => scenario && cutoff(Math.max(0,(Date.parse(scenario.reference_at)-Date.parse(scenario.starts_at))/3600000-before))}>T-{before}h</button>)}</div><p className="limit-note">Only records observed and available by this cutoff can reach facility tools.</p></>}
  </section>;
}
