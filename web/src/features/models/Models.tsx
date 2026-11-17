import { useEffect, useState } from 'react';
import { api, type Model } from '../../lib/api';

const datasets = ['FD001', 'FD002', 'FD003', 'FD004'];
export function Models() {
  const [dataset, setDataset] = useState('FD001');
  const [models, setModels] = useState<Model[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    api<{ models: Model[] }>('/predictions/models').then(d => { if (live) setModels(d.models); }).catch(e => setError(e.message));
    return () => { live = false; };
  }, []);
  const groups = [...new Set(models.map(m => `${m.route} / ${m.variant}`))];
  return <section className="page">
    <div className="page-title"><div className="section-label">Preserved native artifacts</div><h1>Model catalog</h1><p>Availability is based on recorded real inference checks. Historical metrics describe saved experiments; they are not a new evaluation.</p></div>
    {error && <p className="error">{error}</p>}
    <details className="coverage"><summary>Family and dataset coverage</summary><div className="coverage-scroll"><table><thead><tr><th>Family / variant</th>{datasets.map(d => <th key={d}>{d}</th>)}</tr></thead><tbody>{groups.map(group => <tr key={group}><th>{group}</th>{datasets.map(d => { const entries = models.filter(m => m.dataset === d && `${m.route} / ${m.variant}` === group); return <td key={d}>{entries.filter(m => m.status === 'ready').length}/{entries.length} inferred</td>; })}</tr>)}</tbody></table></div><p className="muted">Counts cover discovered saved seeds. A successful inference check is not a diagnostic accuracy benchmark.</p></details>
    <label>Dataset<select aria-label="Catalog dataset" value={dataset} onChange={e => setDataset(e.target.value)}>{datasets.map(x => <option key={x}>{x}</option>)}</select></label>
    <div className="catalog">{models.filter(m => m.dataset === dataset).map(m => <details key={m.model_id}><summary><span><strong>{m.route}</strong><small>{m.variant} / seed {m.seed} / {m.purpose}</small></span><span className={`tag ${m.status === 'ready' ? 'complete' : ''}`}>{m.status.replaceAll('_', ' ')}</span></summary><p>{m.model_id}</p><p>Input features: {m.feature_schema?.join(', ')}<br/>Window: {m.window_length ?? 'native policy'}</p><p className="muted">{m.artifact_dir}</p>{m.verification?.error && <p className="error">{m.verification.error}</p>}<h4>Archived experiment metrics</h4>{Object.keys(m.historical_metrics ?? {}).length ? <pre>{JSON.stringify(m.historical_metrics, null, 2)}</pre> : <p>No historical metrics file was found for this exact saved run.</p>}</details>)}</div>
  </section>;
}
