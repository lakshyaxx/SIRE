import { useId } from 'react';

export type Relation = { source: string; target: string; relation: string; valid_from: string };

/** Display only returned, historically valid edges; direction is not a causal claim. */
export function AssetGraph({ relations, selected }: { relations: Relation[]; selected: string }) {
  const marker = `edge-${useId().replaceAll(':', '')}`;
  const nodes = [...new Set([selected, ...relations.flatMap(edge => [edge.source, edge.target])])].sort();
  const columns = Math.min(3, nodes.length);
  const height = Math.max(180, Math.ceil(nodes.length / columns) * 140);
  const positions = new Map(nodes.map((id, i) => [id, { x: 100 + (i % columns) * 190, y: 65 + Math.floor(i / columns) * 140 }]));
  return <figure className="asset-graph">
    <svg viewBox={`0 0 ${columns * 190 + 10} ${height}`} role="img" aria-label={`Recorded dependencies around ${selected}`}>
      <title>Historically valid directed asset dependencies</title>
      <desc>{relations.length ? relations.map(edge => `${edge.source} to ${edge.target}: ${edge.relation.replaceAll('_', ' ')}`).join('; ') : 'No dependency edges returned at this cutoff.'}</desc>
      <defs><marker id={marker} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" /></marker></defs>
      {relations.map((edge, i) => {
        const from = positions.get(edge.source)!; const to = positions.get(edge.target)!;
        const length = Math.hypot(to.x - from.x, to.y - from.y);
        if (!length) return null;
        const dx = (to.x - from.x) / length; const dy = (to.y - from.y) / length;
        return <line key={`${edge.source}-${edge.target}-${i}`} x1={from.x + dx * 48} y1={from.y + dy * 30} x2={to.x - dx * 52} y2={to.y - dy * 34} stroke="currentColor" strokeWidth="1.5" markerEnd={`url(#${marker})`}><title>{edge.relation.replaceAll('_', ' ')}; valid {edge.valid_from}</title></line>;
      })}
      {nodes.map(id => {
        const point = positions.get(id)!;
        return <g key={id} transform={`translate(${point.x}, ${point.y})`}><rect x="-59" y="-24" width="118" height="48" rx="9" fill={id === selected ? '#e1eee8' : '#f7f8f6'} stroke="currentColor" /><text textAnchor="middle" dominantBaseline="middle" fontSize="13" fill="currentColor">{id}</text></g>;
      })}
    </svg>
    <figcaption className="muted">Arrows show recorded dependency direction at the selected cutoff. Exact relation types and validity times follow.</figcaption>
  </figure>;
}
