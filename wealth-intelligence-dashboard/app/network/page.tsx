'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  ChevronRight,
  GitFork,
  Search,
  ShieldCheck,
  Sparkles,
  Users,
} from 'lucide-react';

type Capability = {
  id: string;
  label: string;
  offeringType: string;
  evidenceLevel: string;
  availability: string;
  basis?: string;
  confidence?: number;
};

type Need = {
  needId: string;
  title: string;
  needType: string;
  urgency: string;
  candidateCount: number;
};

type Actor = {
  actorId: string;
  actorType: 'rm' | 'client' | 'bank_team' | 'external_organization' | 'public_individual' | 'public_organization';
  name: string;
  organization: string | null;
  jurisdiction: string;
  networkTier: number;
  capabilities: Capability[];
  needs: Need[];
  description?: string | null;
  prominenceScore?: number | null;
  sourceUrl?: string;
  reviewStatus?: string;
};

type Relationship = {
  relationshipId: string;
  source: string;
  target: string;
  relationshipType: string;
  networkTier: number;
  strength: number;
};

type Opportunity = {
  needId: string;
  clientId: string;
  providerId: string;
  providerName: string;
  routeTier: number;
  score: number;
  recommended: boolean;
};

type GraphData = {
  asOf: string;
  rmActorId: string;
  nodes: Actor[];
  edges: Relationship[];
  opportunities: Opportunity[];
};

type PublicSnapshot = {
  asOf: string;
  status: string;
  actors: {
    sourceId: string;
    actorType: 'individual' | 'organization';
    name: string;
    description: string | null;
    country: string | null;
    prominenceScore: number | null;
    sourceUrl: string;
    reviewStatus: string;
    capabilities: { id: string; label: string; basis: string; confidence: number; reviewStatus: string }[];
  }[];
  relationships: {
    relationshipId: string;
    source: string;
    target: string;
    relationshipType: string;
    reviewStatus: string;
    sourceUrl: string;
  }[];
};

type Position = { x: number; y: number; width: number };

const TYPE_LABELS: Record<Actor['actorType'], string> = {
  rm: 'Relationship manager',
  client: 'Client',
  bank_team: 'Bank network',
  external_organization: 'External organization',
  public_individual: 'Public figure · pending review',
  public_organization: 'Public organization · pending review',
};

const TYPE_STYLE: Record<Actor['actorType'], { fill: string; stroke: string; dot: string }> = {
  rm: { fill: '#17392f', stroke: '#8ee5b5', dot: '#8ee5b5' },
  client: { fill: '#10211e', stroke: '#42695c', dot: '#8ee5b5' },
  bank_team: { fill: '#132236', stroke: '#5678a5', dot: '#7db8ff' },
  external_organization: { fill: '#251d34', stroke: '#745a98', dot: '#b99aff' },
  public_individual: { fill: '#332414', stroke: '#a9773e', dot: '#f3cf78' },
  public_organization: { fill: '#2b2118', stroke: '#745f43', dot: '#c7a875' },
};

const positionColumn = (items: Actor[], xValues: number[], top = 72, bottom = 662) => {
  const positions = new Map<string, Position>();
  const columns = xValues.length;
  const rows = Math.max(1, Math.ceil(items.length / columns));
  const gap = rows === 1 ? 0 : (bottom - top) / (rows - 1);
  items.forEach((actor, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    positions.set(actor.actorId, { x: xValues[column], y: rows === 1 ? (top + bottom) / 2 : top + row * gap, width: actor.actorType === 'client' ? 150 : 178 });
  });
  return positions;
};

const compact = (value: string, max = 22) => value.length <= max ? value : `${value.slice(0, max - 1)}…`;

function Loading() {
  return <main className="grid min-h-screen place-items-center bg-[#07100f] text-white"><p className="text-sm text-white/45">Mapping the relationship network…</p></main>;
}

export default function NetworkPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [selectedId, setSelectedId] = useState('RM-SG-014');
  const [actorType, setActorType] = useState<'all' | Actor['actorType']>('all');
  const [capability, setCapability] = useState('all');
  const [query, setQuery] = useState('');
  const [needsOnly, setNeedsOnly] = useState(false);
  const [showOpportunities, setShowOpportunities] = useState(true);

  useEffect(() => {
    void Promise.all([
      fetch('/data/network-graph.json').then((response) => response.json() as Promise<GraphData>),
      fetch('/data/public-network-staging.json').then((response) => response.json() as Promise<PublicSnapshot>),
    ]).then(([payload, staging]) => {
      const publicNodes: Actor[] = staging.actors.map((actor) => ({
        actorId: `PUB-${actor.sourceId}`,
        actorType: actor.actorType === 'individual' ? 'public_individual' : 'public_organization',
        name: actor.name,
        organization: null,
        jurisdiction: actor.country ?? 'Public record',
        networkTier: 3,
        needs: [],
        capabilities: actor.capabilities.map((item) => ({
          id: item.id,
          label: item.label,
          offeringType: 'public signal',
          evidenceLevel: 'inferred',
          availability: 'unknown',
          basis: item.basis,
          confidence: item.confidence,
        })),
        description: actor.description,
        prominenceScore: actor.prominenceScore,
        sourceUrl: actor.sourceUrl,
        reviewStatus: actor.reviewStatus,
      }));
      const publicEdges: Relationship[] = staging.relationships.map((edge) => ({
        relationshipId: edge.relationshipId,
        source: `PUB-${edge.source}`,
        target: `PUB-${edge.target}`,
        relationshipType: edge.relationshipType,
        networkTier: 3,
        strength: 35,
      }));
      const merged = { ...payload, nodes: [...payload.nodes, ...publicNodes], edges: [...payload.edges, ...publicEdges] };
      setData(merged);
      const focus = new URLSearchParams(window.location.search).get('focus');
      if (focus && merged.nodes.some((node) => node.actorId === focus)) setSelectedId(focus);
    });
  }, []);

  const capabilities = useMemo(() => {
    if (!data) return [];
    return Array.from(new Map(data.nodes.flatMap((node) => node.capabilities).map((item) => [item.id, item.label])).entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [data]);

  const visibleNodes = useMemo(() => {
    if (!data) return [];
    const needle = query.trim().toLowerCase();
    return data.nodes.filter((node) => {
      if (node.actorId === data.rmActorId) return true;
      if (actorType !== 'all' && node.actorType !== actorType) return false;
      if (capability !== 'all' && !node.capabilities.some((item) => item.id === capability)) return false;
      if (needsOnly && node.actorType === 'client' && node.needs.length === 0) return false;
      if (needle && !`${node.name} ${node.organization ?? ''} ${node.jurisdiction}`.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [actorType, capability, data, needsOnly, query]);

  const positions = useMemo(() => {
    const result = new Map<string, Position>();
    if (!data) return result;
    result.set(data.rmActorId, { x: 82, y: 367, width: 128 });
    const clients = visibleNodes.filter((node) => node.actorType === 'client');
    const bank = visibleNodes.filter((node) => node.actorType === 'bank_team');
    const external = visibleNodes.filter((node) => node.actorType === 'external_organization');
    const publicPeople = visibleNodes.filter((node) => node.actorType === 'public_individual');
    const publicOrganizations = visibleNodes.filter((node) => node.actorType === 'public_organization');
    positionColumn(clients, [300, 482]).forEach((value, key) => result.set(key, value));
    positionColumn(bank, [742], 82, 652).forEach((value, key) => result.set(key, value));
    positionColumn(external, [1015], 200, 534).forEach((value, key) => result.set(key, value));
    positionColumn(publicPeople, [285, 485], 792, 1002).forEach((value, key) => result.set(key, value));
    positionColumn(publicOrganizations, [760, 985], 772, 1022).forEach((value, key) => result.set(key, value));
    return result;
  }, [data, visibleNodes]);

  if (!data) return <Loading />;

  const visibleIds = new Set(visibleNodes.map((node) => node.actorId));
  const structuralEdges = data.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
  const recommendedEdges = Array.from(new Map(data.opportunities
    .filter((item) => item.recommended && visibleIds.has(item.clientId) && visibleIds.has(item.providerId))
    .map((item) => [`${item.clientId}:${item.providerId}`, item])).values());
  const selected = data.nodes.find((node) => node.actorId === selectedId) ?? data.nodes.find((node) => node.actorId === data.rmActorId)!;
  const selectedRelationships = data.edges.filter((edge) => edge.source === selected.actorId || edge.target === selected.actorId);
  const selectedOpportunities = data.opportunities.filter((item) => item.clientId === selected.actorId || item.providerId === selected.actorId);
  const isIncident = (source: string, target: string) => selected.actorId === source || selected.actorId === target;

  return (
    <div className="min-h-screen bg-[#07100f] text-[#f4f7f3]">
      <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#07100f]/92 px-4 py-3 backdrop-blur-xl sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl border border-[#8ee5b5]/25 bg-[#8ee5b5]/10"><Sparkles className="h-4 w-4 text-[#8ee5b5]" /></span>
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#8ee5b5]">Access Alpha</p><h1 className="text-[15px] font-semibold tracking-tight">Network intelligence</h1></div>
          </Link>
          <Link href="/" className="flex items-center gap-2 text-xs text-white/48 transition hover:text-white"><ArrowLeft className="h-4 w-4" />Back to workbench</Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
          <div><p className="eyebrow">Relationship capital</p><h2 className="page-title">See the paths behind every introduction.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">Explore clients, bank teams and illustrative external organizations. Dashed lines show recommended need-to-provider matches.</p></div>
          <div className="flex flex-wrap gap-4 text-[10px] text-white/42">
            {(['client', 'bank_team', 'external_organization', 'public_individual'] as const).map((type) => <span key={type} className="flex items-center gap-2"><i className="h-2 w-2 rounded-full" style={{ background: TYPE_STYLE[type].dot }} />{type === 'public_individual' ? 'Public staging' : TYPE_LABELS[type]}</span>)}
          </div>
        </div>

        <section aria-label="Network filters" className="mt-6 flex flex-wrap items-end gap-3 border-y border-white/[0.07] py-4">
          <label className="relative min-w-[220px] flex-1"><span className="sr-only">Search actors</span><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/28" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search people or organizations" className="graph-control w-full pl-10" /></label>
          <label><span className="mb-1.5 block text-[9px] uppercase tracking-[0.12em] text-white/30">Actor type</span><select value={actorType} onChange={(event) => setActorType(event.target.value as typeof actorType)} className="graph-control min-w-[170px]"><option value="all">All actors</option><option value="client">Clients</option><option value="bank_team">Bank network</option><option value="external_organization">External organizations</option><option value="public_individual">Public figures · pending</option><option value="public_organization">Public organizations · pending</option></select></label>
          <label><span className="mb-1.5 block text-[9px] uppercase tracking-[0.12em] text-white/30">Capability</span><select value={capability} onChange={(event) => setCapability(event.target.value)} className="graph-control min-w-[210px]"><option value="all">All capabilities</option>{capabilities.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
          <label className="flex h-10 items-center gap-2 rounded-xl border border-white/[0.09] px-3 text-xs text-white/58"><input type="checkbox" checked={needsOnly} onChange={(event) => setNeedsOnly(event.target.checked)} />Clients with needs</label>
          <label className="flex h-10 items-center gap-2 rounded-xl border border-white/[0.09] px-3 text-xs text-white/58"><input type="checkbox" checked={showOpportunities} onChange={(event) => setShowOpportunities(event.target.checked)} />Suggested matches</label>
        </section>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_330px]">
          <section className="panel min-w-0 overflow-hidden p-0" aria-labelledby="network-graph-title">
            <div className="panel-heading px-5 pt-5 sm:px-6 sm:pt-6"><div><h3 id="network-graph-title" className="panel-title">Relationship network</h3><p className="panel-subtitle">{visibleNodes.length} actors · {structuralEdges.length} known relationships{showOpportunities ? ` · ${recommendedEdges.length} suggested matches` : ''}</p></div><GitFork className="h-4 w-4 text-[#8ee5b5]" /></div>
            <div className="mt-3 overflow-x-auto pb-3">
              <svg viewBox="0 0 1120 1060" className="h-auto min-w-[920px]" aria-labelledby="network-svg-title network-svg-desc">
                <title id="network-svg-title">Relationship and opportunity network</title>
                <desc id="network-svg-desc">Known RM relationships are shown as solid lines. Recommended matches between client needs and providers are shown as dashed lines.</desc>
                <g aria-hidden="true">
                  {[['RM', 82], ['CLIENTS', 390], ['BANK NETWORK', 742], ['EXTERNAL', 1015]].map(([label, x]) => <text key={String(label)} x={Number(x)} y="28" textAnchor="middle" className="graph-node-meta">{String(label)}</text>)}
                  <line x1="188" y1="45" x2="188" y2="704" stroke="rgba(255,255,255,.06)" />
                  <line x1="610" y1="45" x2="610" y2="704" stroke="rgba(255,255,255,.06)" />
                  <line x1="884" y1="45" x2="884" y2="704" stroke="rgba(255,255,255,.06)" />
                  <line x1="35" y1="724" x2="1085" y2="724" stroke="rgba(243,207,120,.16)" />
                  <text x="55" y="750" className="graph-node-meta" fill="#f3cf78">PUBLIC DATA · PENDING REVIEW</text>
                </g>

                <g aria-label="Known relationship paths">
                  {structuralEdges.map((edge) => {
                    const source = positions.get(edge.source); const target = positions.get(edge.target);
                    if (!source || !target) return null;
                    return <line key={edge.relationshipId} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke={isIncident(edge.source, edge.target) ? 'rgba(142,229,181,.7)' : 'rgba(255,255,255,.11)'} strokeWidth={isIncident(edge.source, edge.target) ? 2 : 1}><title>{edge.relationshipType.replaceAll('_', ' ')} · strength {edge.strength}</title></line>;
                  })}
                </g>

                {showOpportunities && <g aria-label="Recommended opportunity matches">
                  {recommendedEdges.map((edge) => {
                    const source = positions.get(edge.clientId); const target = positions.get(edge.providerId);
                    if (!source || !target) return null;
                    return <path key={`${edge.clientId}:${edge.providerId}`} d={`M ${source.x} ${source.y} C ${(source.x + target.x) / 2} ${source.y}, ${(source.x + target.x) / 2} ${target.y}, ${target.x} ${target.y}`} fill="none" stroke={isIncident(edge.clientId, edge.providerId) ? '#f3cf78' : 'rgba(243,207,120,.42)'} strokeWidth={isIncident(edge.clientId, edge.providerId) ? 2.5 : 1.5} strokeDasharray="5 5"><title>Suggested route · score {edge.score}</title></path>;
                  })}
                </g>}

                <g aria-label="Network actors">
                  {visibleNodes.map((node) => {
                    const point = positions.get(node.actorId); if (!point) return null;
                    const style = TYPE_STYLE[node.actorType];
                    const active = selected.actorId === node.actorId;
                    return <a key={node.actorId} href={`#${node.actorId}`} onClick={(event) => { event.preventDefault(); setSelectedId(node.actorId); }} aria-label={`${node.name}, ${TYPE_LABELS[node.actorType]}`}>
                      <rect x={point.x - point.width / 2} y={point.y - 25} width={point.width} height="50" rx="12" fill={style.fill} stroke={active ? '#f4f7f3' : style.stroke} strokeWidth={active ? 2.5 : 1} />
                      <circle cx={point.x - point.width / 2 + 13} cy={point.y - 10} r="3.5" fill={style.dot} />
                      <text x={point.x - point.width / 2 + 22} y={point.y - 6} className="graph-node-label">{compact(node.name, node.actorType === 'client' ? 18 : 22)}</text>
                      <text x={point.x - point.width / 2 + 13} y={point.y + 13} className="graph-node-meta">{node.actorType === 'client' ? `${node.needs.length} NEED${node.needs.length === 1 ? '' : 'S'} · TIER ${node.networkTier}` : node.actorType === 'rm' ? 'NETWORK OWNER' : node.actorType.startsWith('public_') ? `PENDING REVIEW${node.prominenceScore ? ` · ${node.prominenceScore} SITELINKS` : ''}` : `TIER ${node.networkTier} · ${node.capabilities.length} CAPABILIT${node.capabilities.length === 1 ? 'Y' : 'IES'}`}</text>
                    </a>;
                  })}
                </g>
              </svg>
            </div>
          </section>

          <aside className="panel h-fit" aria-live="polite">
            <div className="flex items-start justify-between gap-3"><div><span className="soft-label">{TYPE_LABELS[selected.actorType]}</span><h3 className="mt-4 text-xl font-semibold tracking-[-0.025em]">{selected.name}</h3><p className="mt-1 text-[10px] text-white/34">{selected.actorId} · {selected.jurisdiction}</p></div><Users className="h-4 w-4 text-white/28" /></div>

            {selected.description && <p className="mt-4 text-xs leading-5 text-white/48">{selected.description}</p>}
            {selected.sourceUrl && <a href={selected.sourceUrl} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-[10px] text-[#f3cf78]/75 transition hover:text-[#f3cf78]">Open source record <ChevronRight className="h-3.5 w-3.5" /></a>}

            {selected.needs.length > 0 && <div className="mt-6"><p className="text-[9px] font-semibold uppercase tracking-[0.13em] text-white/28">Active client needs</p><div className="mt-3 space-y-2">{selected.needs.map((need) => <Link key={need.needId} href={`/?need=${need.needId}`} className="need-switch"><span><strong>{need.title}</strong><small>{need.urgency} · {need.candidateCount} routes</small></span><ChevronRight className="h-4 w-4" /></Link>)}</div></div>}

            {selected.capabilities.length > 0 && <div className="mt-6"><p className="text-[9px] font-semibold uppercase tracking-[0.13em] text-white/28">Capabilities</p><div className="mt-3 space-y-2">{selected.capabilities.map((item) => <div key={item.id} className="rounded-xl border border-white/[0.07] bg-black/10 p-3"><p className="text-xs font-medium text-white/72">{item.label}</p><p className="mt-1 text-[9px] capitalize text-white/30">{item.offeringType} · {item.evidenceLevel} evidence · {item.availability}</p></div>)}</div></div>}

            <div className="mt-6 grid grid-cols-2 gap-3 border-t border-white/[0.07] pt-5"><div><p className="text-[9px] text-white/28">Relationships</p><p className="mt-1 text-lg font-semibold">{selectedRelationships.length}</p></div><div><p className="text-[9px] text-white/28">Matched routes</p><p className="mt-1 text-lg font-semibold">{selectedOpportunities.filter((item) => item.recommended).length}</p></div></div>

            <div className="mt-5 flex gap-2 border-t border-white/[0.07] pt-4 text-[10px] leading-4 text-white/38"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#f3cf78]" /><p>{selected.actorType.startsWith('public_') ? 'This is public-data review staging. It is not a verified bank relationship and cannot be used for an introduction until approved.' : 'Suggested paths are decision support. Consent and suitability checks are required before any introduction.'}</p></div>
          </aside>
        </div>
      </main>
    </div>
  );
}
