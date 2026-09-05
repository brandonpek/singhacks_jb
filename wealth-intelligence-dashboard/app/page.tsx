'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Bell,
  BriefcaseBusiness,
  CalendarClock,
  ChevronRight,
  CircleDollarSign,
  GitFork,
  Handshake,
  LayoutDashboard,
  LineChart as LineChartIcon,
  Search,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
  WalletCards,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from 'recharts';
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select';

type Datum = { name: string; value: number; usd?: number };
type TimelinePoint = { date: string; value: number };
type Client = {
  id: string;
  name: string;
  bookingCentre: string;
  wealthBand: string;
  baseCurrency: string;
  aum: number;
  lifeStage: string;
  riskProfile: string;
  riskTolerance: number;
  liquidityNeeds: string;
  objectives: string;
  priorityScore: number;
  priority: 'Critical' | 'High' | 'Watch' | 'Stable';
  reasons: string[];
  allocationBreaches: { portfolioId: string; portfolio: string; assetClass: string; actual: number; min: number; max: number }[];
  concentrationBreaches: { instrument: string; actual: number; limit: number }[];
  sustainabilityBreaches: string[];
  illiquidPct: number;
  allocation: Datum[];
  liquidity: Datum[];
  history: TimelinePoint[];
  topPositions: { id: string; name: string; value: number; weight: number }[];
  facilities: { type: string; trigger: number; current: number; history: { date: string; ltv: number }[] }[];
  cashNeeds: { description: string; amount: number; currency: string; due: string; certainty: string }[];
  commitments: { fund: string; uncalled: number; currency: string; window: string }[];
  latestNote: { note_date: string; channel: string; note: string } | null;
};
type DashboardData = {
  asOf: string;
  summary: { totalAum: number; clientCount: number; portfolioCount: number; uhnwCount: number; allocationFlagPortfolios: number; dailyLiquidityPct: number; illiquidPct: number };
  bookHistory: TimelinePoint[];
  bookAllocation: Datum[];
  bookLiquidity: Datum[];
  marketSeries: { id: string; name: string; values: { date: string; raw: number; index: number }[] }[];
  events: { event_date: string; description: string; primary_transmission: string; severity: string }[];
  clients: Client[];
};
type NetworkCandidate = {
  opportunityId: string;
  providerId: string;
  providerName: string;
  providerType: 'client' | 'bank_team' | 'external_organization';
  routeTier: 1 | 2 | 3;
  routeLabel: string;
  score: number;
  capability: string;
  offeringType: string;
  rationale: string;
  capabilityDescription: string;
  evidenceLevel: string;
  availability: string;
  permission: string;
  path: string[];
  nextAction: string;
  recommended: boolean;
};
type NetworkNeed = {
  needId: string;
  clientId: string;
  clientName: string;
  needType: string;
  title: string;
  description: string;
  amount: number | null;
  currency: string | null;
  dueFrom: string | null;
  urgency: string;
  certainty: string;
  usedTiers: number[];
  candidates: NetworkCandidate[];
};
type NetworkData = { asOf: string; minimumQualifiedOptions: number; needs: NetworkNeed[] };

const CHART_COLORS = ['#8ee5b5', '#7db8ff', '#b99aff', '#f3cf78', '#ff8c87', '#82d7d1'];
const priorityStyles = {
  Critical: 'border-[#ff8c87]/30 bg-[#ff8c87]/10 text-[#ffaaa6]',
  High: 'border-[#f3cf78]/30 bg-[#f3cf78]/10 text-[#f3cf78]',
  Watch: 'border-[#7db8ff]/30 bg-[#7db8ff]/10 text-[#93c5fd]',
  Stable: 'border-[#8ee5b5]/30 bg-[#8ee5b5]/10 text-[#8ee5b5]',
};

const money = (value: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1 }).format(value);
const localMoney = (value: number, currency: string) =>
  `${currency} ${new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}`;
const shortDate = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
const chartDate = (value: string) => new Date(`${value}T00:00:00`).toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });

function StatCard({ label, value, note, icon: Icon, tone = 'mint' }: { label: string; value: string; note: string; icon: typeof Users; tone?: 'mint' | 'amber' }) {
  return (
    <article className="metric-card">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[12px] font-medium text-white/52">{label}</p>
        <span className={tone === 'amber' ? 'icon-wrap amber' : 'icon-wrap'}><Icon className="h-4 w-4" /></span>
      </div>
      <p className="mt-5 text-[29px] font-semibold tracking-[-0.045em]">{value}</p>
      <p className="mt-1 text-[11px] text-white/38">{note}</p>
    </article>
  );
}

function EmptyState() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#07100f] text-white">
      <div className="text-center"><div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-[#8ee5b5]/25 border-t-[#8ee5b5]" /><p className="text-sm text-white/55">Preparing the wealth intelligence brief…</p></div>
    </main>
  );
}

export default function Home() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [networkData, setNetworkData] = useState<NetworkData | null>(null);
  const [view, setView] = useState<'overview' | 'clients' | 'opportunities' | 'market'>('opportunities');
  const [selectedClientId, setSelectedClientId] = useState('CL-0002');
  const [selectedNeedId, setSelectedNeedId] = useState('CN-013');
  const [query, setQuery] = useState('');

  useEffect(() => {
    void fetch('/data/dashboard.json').then((response) => response.json() as Promise<DashboardData>).then(setData);
    void fetch('/data/network-matches.json').then((response) => response.json() as Promise<NetworkData>).then(setNetworkData);
  }, []);

  useEffect(() => {
    if (!data || !networkData) return;
    const params = new URLSearchParams(window.location.search);
    const needId = params.get('need');
    const clientId = params.get('client');
    const need = needId ? networkData.needs.find((item) => item.needId === needId) : undefined;
    const client = clientId ? data.clients.find((item) => item.id === clientId) : undefined;
    queueMicrotask(() => {
      if (need) {
        setSelectedNeedId(need.needId);
        setSelectedClientId(need.clientId);
        setView('opportunities');
      } else if (client) {
        setSelectedClientId(client.id);
        setView('clients');
      }
    });
  }, [data, networkData]);

  useEffect(() => {
    if (!data) return;
    const context = (document as Document & {
      modelContext?: {
        registerTool: (tool: unknown, options?: { signal?: AbortSignal }) => void | Promise<void>;
      };
    }).modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    void Promise.resolve(context.registerTool({
      name: 'navigate_to_client_brief',
      title: 'Open client brief',
      description: 'Open the visible wealth-intelligence brief for one client using a CL-nnnn client ID.',
      inputSchema: {
        type: 'object',
        properties: { clientId: { type: 'string', pattern: '^CL-[0-9]{4}$' } },
        required: ['clientId'],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true, untrustedContentHint: false },
      execute(input: unknown) {
        const clientId = typeof input === 'object' && input !== null && 'clientId' in input
          ? String((input as { clientId: unknown }).clientId)
          : '';
        const client = data.clients.find((item) => item.id === clientId);
        if (!client) throw new Error(`Unknown client ID: ${clientId}`);
        setSelectedClientId(client.id);
        setView('clients');
        return { clientId: client.id, clientName: client.name, view: 'client intelligence' };
      },
    }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  }, [data]);

  useEffect(() => {
    if (!networkData) return;
    const context = (document as Document & {
      modelContext?: { registerTool: (tool: unknown, options?: { signal?: AbortSignal }) => void | Promise<void> };
    }).modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    void Promise.resolve(context.registerTool({
      name: 'open_collaboration_routes',
      title: 'Open collaboration routes',
      description: 'Open ranked RM, bank and external routes for a client need using its need ID.',
      inputSchema: {
        type: 'object',
        properties: { needId: { type: 'string', pattern: '^(CN|SN)-[0-9]{3}$' } },
        required: ['needId'],
        additionalProperties: false,
      },
      annotations: { readOnlyHint: true, untrustedContentHint: false },
      execute(input: unknown) {
        const needId = typeof input === 'object' && input !== null && 'needId' in input
          ? String((input as { needId: unknown }).needId)
          : '';
        const need = networkData.needs.find((item) => item.needId === needId);
        if (!need) throw new Error(`Unknown need ID: ${needId}`);
        setSelectedNeedId(need.needId);
        setView('opportunities');
        return { needId: need.needId, clientName: need.clientName, candidateCount: need.candidates.length };
      },
    }, { signal: lifecycle.signal })).catch(() => undefined);
    return () => lifecycle.abort();
  }, [networkData]);

  const selectedClient = data?.clients.find((client) => client.id === selectedClientId) ?? data?.clients[0];
  const selectedNeed = networkData?.needs.find((need) => need.needId === selectedNeedId) ?? networkData?.needs[0];
  const clientNeeds = networkData?.needs.filter((need) => need.clientId === selectedClient?.id) ?? [];
  const opportunityClientNeeds = networkData?.needs.filter((need) => need.clientId === selectedNeed?.clientId) ?? [];
  const filteredClients = useMemo(() => data?.clients.filter((client) => `${client.name} ${client.id}`.toLowerCase().includes(query.toLowerCase())) ?? [], [data, query]);
  const marketData = useMemo(() => {
    if (!data) return [];
    return data.bookHistory.map(({ date }) => {
      const point: Record<string, string | number> = { date };
      data.marketSeries.forEach((series) => { point[series.id] = series.values.find((item) => item.date === date)?.index ?? 0; });
      return point;
    });
  }, [data]);

  if (!data || !selectedClient || !networkData || !selectedNeed) return <EmptyState />;

  const openClient = (client: Client) => { setSelectedClientId(client.id); setView('clients'); };
  const openRoutesForClient = (clientId: string) => {
    const need = networkData.needs.find((item) => item.clientId === clientId);
    if (need) setSelectedNeedId(need.needId);
    setView('opportunities');
  };

  return (
    <div className="min-h-screen bg-[#07100f] text-[#f4f7f3]">
      <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#07100f]/92 px-4 py-3 backdrop-blur-xl sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-xl border border-[#8ee5b5]/25 bg-[#8ee5b5]/10"><Sparkles className="h-4 w-4 text-[#8ee5b5]" /></span>
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#8ee5b5]">Access Alpha</p><h1 className="text-[15px] font-semibold tracking-tight">Relationship Intelligence</h1></div>
          </div>
          <div className="flex items-center gap-2 text-sm text-white/50">
            <span className="hidden sm:inline">As of 26 Aug 2026</span>
            <button aria-label="Notifications" className="rounded-full border border-white/10 p-2.5 transition hover:border-white/20 hover:bg-white/5"><Bell className="h-4 w-4" /></button>
            <span className="grid h-9 w-9 place-items-center rounded-full bg-[#d1f7e0] text-xs font-bold text-[#0b2c23]">PO</span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1600px] lg:grid-cols-[205px_minmax(0,1fr)]">
        <aside className="hidden min-h-[calc(100vh-66px)] border-r border-white/[0.07] p-4 lg:flex lg:flex-col">
          <p className="mb-3 px-3 text-[9px] font-semibold uppercase tracking-[0.18em] text-white/28">Workbench</p>
          <nav className="space-y-1">
            {[
              ['overview', 'Morning brief', LayoutDashboard],
              ['clients', 'Client explorer', Users],
              ['opportunities', 'Opportunity routes', GitFork],
              ['market', 'Market & events', LineChartIcon],
            ].map(([id, label, Icon]) => (
              <button key={String(id)} onClick={() => setView(id as typeof view)} className={`nav-item ${view === id ? 'active' : ''}`}><Icon className="h-4 w-4" />{String(label)}</button>
            ))}
            <Link href="/network" className="nav-item"><GitFork className="h-4 w-4" />Network map</Link>
          </nav>
          <div className="mt-auto rounded-2xl border border-white/[0.08] bg-white/[0.035] p-4">
            <ShieldCheck className="h-5 w-5 text-[#8ee5b5]" />
            <p className="mt-3 text-xs font-medium">Controlled intelligence</p>
            <p className="mt-1 text-[10px] leading-4 text-white/35">Events are grounded in the approved 2026 event log. RM review remains required.</p>
          </div>
        </aside>

        <main className="min-w-0 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mb-5 flex gap-1 overflow-x-auto lg:hidden">
            {[
              ['overview', 'Brief'], ['clients', 'Clients'], ['opportunities', 'Routes'], ['market', 'Market'],
            ].map(([id, label]) => <button key={id} onClick={() => setView(id as typeof view)} className={`mobile-tab ${view === id ? 'active' : ''}`}>{label}</button>)}
            <Link href="/network" className="mobile-tab">Network</Link>
          </div>

          {view === 'overview' && (
            <section>
              <div className="mb-7 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
                <div><p className="eyebrow">RM morning brief</p><h2 className="page-title">Focus attention where it changes the conversation.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">One book, twenty clients, and a ranked view of portfolio signals that need human judgement.</p></div>
                <button onClick={() => openClient(data.clients[0])} className="primary-button">Review top-priority client <ArrowRight className="h-4 w-4" /></button>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Book AUM" value={money(data.summary.totalAum)} note={`Across ${data.summary.portfolioCount} portfolios`} icon={BriefcaseBusiness} />
                <StatCard label="Client relationships" value={String(data.summary.clientCount)} note={`${data.summary.uhnwCount} UHNW · ${data.summary.clientCount - data.summary.uhnwCount} HNW`} icon={Users} />
                <StatCard label="Allocation flags" value={String(data.summary.allocationFlagPortfolios)} note="Managed portfolios outside a band" icon={AlertTriangle} tone="amber" />
                <StatCard label="Daily liquidity" value={`${data.summary.dailyLiquidityPct}%`} note={`${data.summary.illiquidPct}% remains illiquid`} icon={WalletCards} />
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                <article className="panel">
                  <div className="panel-heading"><div><p className="panel-title">Book value across snapshots</p><p className="panel-subtitle">USD millions · includes flows and FX effects</p></div><span className="soft-label">5 snapshots</span></div>
                  <ChartContainer config={{ value: { label: 'Book AUM', color: '#8ee5b5' } }} className="mt-4 h-[255px] w-full">
                    <AreaChart data={data.bookHistory} margin={{ top: 12, right: 10, bottom: 0, left: -12 }}>
                      <defs><linearGradient id="bookFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8ee5b5" stopOpacity={0.3} /><stop offset="100%" stopColor="#8ee5b5" stopOpacity={0} /></linearGradient></defs>
                      <CartesianGrid vertical={false} stroke="rgba(255,255,255,.07)" />
                      <XAxis dataKey="date" tickFormatter={chartDate} axisLine={false} tickLine={false} tickMargin={10} />
                      <YAxis domain={['dataMin - 8', 'dataMax + 8']} axisLine={false} tickLine={false} tickFormatter={(value) => `$${value}m`} />
                      <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
                      <Area type="monotone" dataKey="value" stroke="#8ee5b5" strokeWidth={2.5} fill="url(#bookFill)" dot={{ fill: '#07100f', stroke: '#8ee5b5', strokeWidth: 2, r: 4 }} />
                    </AreaChart>
                  </ChartContainer>
                </article>

                <article className="panel">
                  <div className="panel-heading"><div><p className="panel-title">Current asset mix</p><p className="panel-subtitle">USD share of the total book</p></div><CircleDollarSign className="h-4 w-4 text-white/30" /></div>
                  <div className="mt-4 grid grid-cols-[145px_1fr] items-center gap-2">
                    <ChartContainer config={{ value: { label: 'Allocation', color: '#8ee5b5' } }} className="h-[190px] w-[145px]">
                      <PieChart><Pie data={data.bookAllocation} dataKey="value" nameKey="name" innerRadius={48} outerRadius={68} paddingAngle={3}>{data.bookAllocation.map((item, index) => <Cell key={item.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />)}</Pie><ChartTooltip content={<ChartTooltipContent hideLabel />} /></PieChart>
                    </ChartContainer>
                    <div className="space-y-2.5">{data.bookAllocation.map((item, index) => <div key={item.name} className="flex items-center justify-between gap-3 text-xs"><span className="flex min-w-0 items-center gap-2 text-white/50"><i className="h-2 w-2 shrink-0 rounded-full" style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} /><span className="truncate">{item.name}</span></span><span className="font-mono text-white/85">{item.value}%</span></div>)}</div>
                  </div>
                </article>
              </div>

              <article className="panel mt-4 overflow-hidden p-0">
                <div className="panel-heading px-5 py-5 sm:px-6"><div><p className="panel-title">Priority clients</p><p className="panel-subtitle">Ranked from portfolio, mandate, liquidity and collateral signals</p></div><button onClick={() => setView('clients')} className="text-link">Explore all <ChevronRight className="h-4 w-4" /></button></div>
                <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Client</th><th>Priority</th><th>Key signal</th><th className="text-right">AUM</th><th><span className="sr-only">Open client</span></th></tr></thead><tbody>{data.clients.slice(0, 8).map((client) => <tr key={client.id} onClick={() => openClient(client)}><td><p className="font-medium text-white/88">{client.name}</p><p className="mt-1 text-[10px] text-white/32">{client.id} · {client.bookingCentre}</p></td><td><span className={`priority-pill ${priorityStyles[client.priority]}`}>{client.priority}</span></td><td className="max-w-[380px] text-white/50">{client.reasons[0] ?? 'No active portfolio flags'}</td><td className="text-right font-mono text-white/75">{money(client.aum)}</td><td><ChevronRight className="ml-auto h-4 w-4 text-white/25" /></td></tr>)}</tbody></table></div>
              </article>
            </section>
          )}

          {view === 'clients' && (
            <section>
              <button onClick={() => setView('overview')} className="mb-4 flex items-center gap-2 text-xs text-white/42 transition hover:text-white"><ArrowLeft className="h-3.5 w-3.5" />Back to morning brief</button>
              <div className="mb-7 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
                <div><p className="eyebrow">Client intelligence</p><h2 className="page-title">{selectedClient.name}</h2><p className="mt-2 text-sm text-white/42">{selectedClient.id} · {selectedClient.bookingCentre} · {selectedClient.wealthBand} · {selectedClient.riskProfile}</p></div>
                <div className="flex w-full flex-col gap-2 sm:flex-row xl:w-auto">
                  <NativeSelect aria-label="Select client" value={selectedClient.id} onChange={(event) => setSelectedClientId(event.target.value)} className="w-full sm:w-[315px]"><NativeSelectOption value="" disabled>Select a client</NativeSelectOption>{data.clients.map((client) => <NativeSelectOption key={client.id} value={client.id}>{client.name}</NativeSelectOption>)}</NativeSelect>
                  {clientNeeds.length > 0 && <button onClick={() => openRoutesForClient(selectedClient.id)} className="primary-button">View {clientNeeds.length} route{clientNeeds.length === 1 ? '' : 's'} <ChevronRight className="h-4 w-4" /></button>}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Current AUM" value={money(selectedClient.aum)} note={`Reported in ${selectedClient.baseCurrency}`} icon={CircleDollarSign} />
                <StatCard label="Priority" value={selectedClient.priority} note={`${selectedClient.priorityScore} weighted signal points`} icon={Activity} tone={selectedClient.priority === 'Critical' || selectedClient.priority === 'High' ? 'amber' : 'mint'} />
                <StatCard label="Risk tolerance" value={`${selectedClient.riskTolerance}/10`} note={selectedClient.riskProfile} icon={ShieldCheck} />
                <StatCard label="Illiquid / gated" value={`${selectedClient.illiquidPct}%`} note={`${selectedClient.liquidityNeeds} stated liquidity need`} icon={WalletCards} tone={selectedClient.illiquidPct > 20 ? 'amber' : 'mint'} />
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
                <article className="panel">
                  <div className="panel-heading"><div><p className="panel-title">Portfolio value</p><p className="panel-subtitle">USD millions across the five snapshots</p></div><Activity className="h-4 w-4 text-[#8ee5b5]" /></div>
                  <ChartContainer config={{ value: { label: 'AUM (USDm)', color: '#7db8ff' } }} className="mt-4 h-[260px] w-full"><AreaChart data={selectedClient.history} margin={{ top: 12, right: 8, bottom: 0, left: -15 }}><defs><linearGradient id="clientFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7db8ff" stopOpacity={0.28} /><stop offset="100%" stopColor="#7db8ff" stopOpacity={0} /></linearGradient></defs><CartesianGrid vertical={false} stroke="rgba(255,255,255,.07)" /><XAxis dataKey="date" tickFormatter={chartDate} axisLine={false} tickLine={false} tickMargin={10} /><YAxis domain={['dataMin - 2', 'dataMax + 2']} axisLine={false} tickLine={false} tickFormatter={(value) => `$${value}m`} /><ChartTooltip content={<ChartTooltipContent indicator="line" />} /><Area type="monotone" dataKey="value" stroke="#7db8ff" strokeWidth={2.5} fill="url(#clientFill)" dot={{ fill: '#07100f', stroke: '#7db8ff', strokeWidth: 2, r: 4 }} /></AreaChart></ChartContainer>
                </article>

                <article className="panel">
                  <div className="panel-heading"><div><p className="panel-title">Asset allocation</p><p className="panel-subtitle">Current client-level exposure</p></div><span className="soft-label">Look across portfolios</span></div>
                  <ChartContainer config={{ value: { label: 'Weight', color: '#b99aff' } }} className="mt-4 h-[260px] w-full"><BarChart data={selectedClient.allocation} layout="vertical" margin={{ top: 5, right: 15, bottom: 0, left: 12 }}><CartesianGrid horizontal={false} stroke="rgba(255,255,255,.07)" /><XAxis type="number" hide domain={[0, 'dataMax + 8']} /><YAxis dataKey="name" type="category" width={96} axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,.45)', fontSize: 10 }} /><ChartTooltip content={<ChartTooltipContent hideLabel />} /><Bar dataKey="value" radius={[0, 7, 7, 0]}>{selectedClient.allocation.map((item, index) => <Cell key={item.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />)}</Bar></BarChart></ChartContainer>
                </article>
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
                <article className="panel">
                  <div className="panel-heading"><div><p className="panel-title">What needs attention</p><p className="panel-subtitle">Evidence before recommendation</p></div><span className={`priority-pill ${priorityStyles[selectedClient.priority]}`}>{selectedClient.priority}</span></div>
                  <div className="mt-5 space-y-3">{selectedClient.reasons.length ? selectedClient.reasons.map((reason, index) => <div key={reason} className="signal-row"><span className="signal-index">{String(index + 1).padStart(2, '0')}</span><p>{reason}</p></div>) : <div className="rounded-xl border border-[#8ee5b5]/15 bg-[#8ee5b5]/5 p-4 text-sm text-[#8ee5b5]">No active portfolio flags in the current rule set.</div>}</div>
                  <div className="mt-5 rounded-2xl border border-white/[0.07] bg-black/15 p-4"><p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/32">Client objective</p><p className="mt-2 text-sm leading-6 text-white/60">{selectedClient.objectives}</p></div>
                </article>

                <article className="panel overflow-hidden p-0">
                  <div className="panel-heading px-5 py-5 sm:px-6"><div><p className="panel-title">Largest positions</p><p className="panel-subtitle">Aggregated across the client relationship</p></div></div>
                  <div className="overflow-x-auto"><table className="data-table compact"><thead><tr><th>Instrument</th><th className="text-right">USD value</th><th className="text-right">Weight</th></tr></thead><tbody>{selectedClient.topPositions.map((position) => <tr key={position.id}><td className="max-w-[390px]"><p className="truncate font-medium text-white/80">{position.name}</p><p className="mt-1 text-[10px] text-white/28">{position.id}</p></td><td className="text-right font-mono text-white/65">${position.value.toFixed(2)}m</td><td className="text-right font-mono text-white/80">{position.weight}%</td></tr>)}</tbody></table></div>
                </article>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <article className="panel"><div className="panel-heading"><div><p className="panel-title">Upcoming obligations</p><p className="panel-subtitle">Cash needs and uncalled commitments</p></div><CalendarClock className="h-4 w-4 text-white/30" /></div><div className="mt-5 space-y-3">{selectedClient.cashNeeds.map((need) => <div key={need.description} className="obligation"><div><p className="text-sm font-medium text-white/75">{need.description}</p><p className="mt-1 text-[10px] text-white/35">Due from {shortDate(need.due)} · {need.certainty}</p></div><span className="font-mono text-sm">{localMoney(need.amount, need.currency)}</span></div>)}{selectedClient.commitments.map((item) => <div key={item.fund} className="obligation"><div><p className="text-sm font-medium text-white/75">{item.fund}</p><p className="mt-1 text-[10px] text-white/35">Uncalled · {item.window}</p></div><span className="font-mono text-sm">{localMoney(item.uncalled, item.currency)}</span></div>)}</div></article>
                <article className="panel"><div className="panel-heading"><div><p className="panel-title">Latest RM context</p><p className="panel-subtitle">Qualitative evidence · not treated as fact</p></div><UserRound className="h-4 w-4 text-white/30" /></div>{selectedClient.latestNote ? <blockquote className="mt-5 border-l-2 border-[#8ee5b5]/45 pl-4 text-sm leading-6 text-white/58">“{selectedClient.latestNote.note}”<footer className="mt-4 text-[10px] font-medium uppercase tracking-[0.12em] text-white/30">{selectedClient.latestNote.note_date} · {selectedClient.latestNote.channel}</footer></blockquote> : <p className="mt-5 text-sm text-white/40">No relationship-manager note is available.</p>}</article>
              </div>
            </section>
          )}

          {view === 'opportunities' && (
            <section>
              <div className="mb-7 flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
                <div>
                  <p className="eyebrow">Relationship capital</p>
                  <h2 className="page-title">Turn a client need into a trusted route.</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">The engine exhausts RM-connected options first, then uses the bank network, and only then considers external routes.</p>
                </div>
                <div className="flex w-full flex-col gap-2 xl:w-[390px]">
                  <NativeSelect aria-label="Select client need" value={selectedNeed.needId} onChange={(event) => setSelectedNeedId(event.target.value)} className="w-full">
                    {networkData.needs.map((need) => <NativeSelectOption key={need.needId} value={need.needId}>{need.clientName} — {need.title}</NativeSelectOption>)}
                  </NativeSelect>
                  <div className="flex flex-wrap gap-3">
                    <button onClick={() => { setSelectedClientId(selectedNeed.clientId); setView('clients'); }} className="text-link">Open client profile <ChevronRight className="h-4 w-4" /></button>
                    <Link href={`/network?focus=${selectedNeed.clientId}`} className="text-link">View in network <ChevronRight className="h-4 w-4" /></Link>
                  </div>
                </div>
              </div>

              <article className="panel overflow-hidden p-0">
                <div className="grid gap-0 xl:grid-cols-[1fr_0.72fr]">
                  <div className="p-5 sm:p-6">
                    <div className="flex flex-wrap items-center gap-2"><span className="soft-label">{selectedNeed.needType}</span><span className={`priority-pill ${selectedNeed.urgency === 'critical' ? priorityStyles.Critical : priorityStyles.High}`}>{selectedNeed.urgency}</span><span className="font-mono text-[10px] text-white/28">{selectedNeed.needId}</span></div>
                    <h3 className="mt-4 text-2xl font-semibold tracking-[-0.035em]">{selectedNeed.clientName}</h3>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-white/52">{selectedNeed.description}</p>
                  </div>
                  <div className="border-t border-white/[0.07] bg-black/10 p-5 sm:p-6 xl:border-l xl:border-t-0">
                    <p className="text-[9px] font-semibold uppercase tracking-[0.13em] text-white/28">Need parameters</p>
                    <div className="mt-4 grid grid-cols-2 gap-5">
                      <div><p className="text-[10px] text-white/32">Amount</p><p className="mt-1 text-lg font-semibold">{selectedNeed.amount && selectedNeed.currency ? localMoney(selectedNeed.amount, selectedNeed.currency) : 'Not specified'}</p></div>
                      <div><p className="text-[10px] text-white/32">Required from</p><p className="mt-1 text-lg font-semibold">{selectedNeed.dueFrom ? shortDate(selectedNeed.dueFrom) : 'Exploratory'}</p></div>
                    </div>
                  </div>
                </div>
              </article>

              <article className="panel mt-4">
                <div className="panel-heading"><div><p className="panel-title">{selectedNeed.clientName}&apos;s needs</p><p className="panel-subtitle">Keep the full client context visible while assessing one route</p></div><span className="soft-label">{opportunityClientNeeds.length} active</span></div>
                <div className="mt-4 grid gap-2 lg:grid-cols-2">
                  {opportunityClientNeeds.map((need) => <button key={need.needId} onClick={() => setSelectedNeedId(need.needId)} aria-pressed={need.needId === selectedNeed.needId} className={`need-switch ${need.needId === selectedNeed.needId ? 'active' : ''}`}><span><strong>{need.title}</strong><small>{need.needType} · {need.urgency}</small></span><ChevronRight className="h-4 w-4" /></button>)}
                </div>
              </article>

              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                {[
                  [1, 'RM connections', 'Clients already known by Priscilla'],
                  [2, 'Bank network', 'Internal specialists and partners'],
                  [3, 'External routes', 'Used only when earlier tiers fall short'],
                ].map(([tier, label, note]) => {
                  const used = selectedNeed.usedTiers.includes(Number(tier));
                  return <div key={String(tier)} className={`route-step ${used ? 'used' : ''}`}><span className="route-number">{tier}</span><div><p className="text-xs font-semibold text-white/72">{String(label)}</p><p className="mt-1 text-[10px] text-white/32">{String(note)}</p></div>{used && <span className="ml-auto text-[9px] font-semibold uppercase tracking-[0.1em] text-[#8ee5b5]">used</span>}</div>;
                })}
              </div>

              <div className="mt-4 grid gap-4 xl:grid-cols-[1.12fr_0.88fr]">
                <article className="panel">
                  <div className="panel-heading"><div><p className="panel-title">Recommended routes</p><p className="panel-subtitle">Minimum {networkData.minimumQualifiedOptions} qualified options, filled tier by tier</p></div><Handshake className="h-4 w-4 text-[#8ee5b5]" /></div>
                  <div className="mt-5 space-y-3">
                    {selectedNeed.candidates.filter((candidate) => candidate.recommended).map((candidate) => (
                      <div key={candidate.opportunityId} className="match-card">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div><div className="flex items-center gap-2"><span className={`tier-pill tier-${candidate.routeTier}`}>{candidate.routeLabel}</span><span className="text-[9px] uppercase tracking-[0.1em] text-white/25">{candidate.evidenceLevel} evidence</span></div><h4 className="mt-3 text-base font-semibold text-white/88">{candidate.providerName}</h4><p className="mt-1 text-[10px] text-white/35">{candidate.capability} · {candidate.offeringType}</p></div>
                          <div className="score-ring"><strong>{candidate.score.toFixed(0)}</strong><span>match</span></div>
                        </div>
                        <p className="mt-4 text-xs leading-5 text-white/52">{candidate.rationale}</p>
                        <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[10px] text-white/35">{candidate.path.map((name, index) => <span key={`${name}-${index}`} className="contents"><span className="rounded-md bg-white/[0.045] px-2 py-1">{name}</span>{index < candidate.path.length - 1 && <ChevronRight className="h-3 w-3" />}</span>)}</div>
                        <div className="mt-4 flex items-center justify-between gap-3 border-t border-white/[0.06] pt-3"><span className="text-[10px] text-[#f3cf78]/70">{candidate.permission === 'granted' ? 'Institutional access confirmed' : 'Identity and contact permission not yet granted'}</span><button className="text-link">{candidate.nextAction}<ChevronRight className="h-3.5 w-3.5" /></button></div>
                      </div>
                    ))}
                    {!selectedNeed.candidates.some((candidate) => candidate.recommended) && <p className="rounded-xl border border-white/[0.07] bg-black/10 p-4 text-sm text-white/42">No qualified route was found. Escalate for manual research without disclosing the client identity.</p>}
                  </div>
                </article>

                <div className="space-y-4">
                  <article className="panel">
                    <div className="panel-heading"><div><p className="panel-title">Reserve routes</p><p className="panel-subtitle">Visible for RM judgement, not promoted ahead of earlier tiers</p></div><GitFork className="h-4 w-4 text-white/30" /></div>
                    <div className="mt-5 space-y-2.5">{selectedNeed.candidates.filter((candidate) => !candidate.recommended).slice(0, 5).map((candidate) => <div key={candidate.opportunityId} className="reserve-row"><span className={`tier-pill tier-${candidate.routeTier}`}>{candidate.routeLabel}</span><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-white/68">{candidate.providerName}</p><p className="mt-1 truncate text-[10px] text-white/30">{candidate.capability}</p></div><span className="font-mono text-[10px] text-white/34">{candidate.score.toFixed(0)}</span></div>)}{!selectedNeed.candidates.some((candidate) => !candidate.recommended) && <p className="text-xs leading-5 text-white/35">No additional route has enough evidence to show.</p>}</div>
                  </article>

                  <article className="rounded-[22px] border border-[#f3cf78]/15 bg-[#f3cf78]/[0.045] p-5 sm:p-6">
                    <ShieldCheck className="h-5 w-5 text-[#f3cf78]" />
                    <p className="mt-4 text-sm font-semibold">The match is not permission</p>
                    <p className="mt-2 text-xs leading-5 text-white/42">Client-derived capabilities remain marked as inferred with unknown availability. Priscilla must confirm interest and obtain consent before revealing either party&apos;s identity.</p>
                  </article>
                </div>
              </div>
            </section>
          )}

          {view === 'market' && (
            <section>
              <div className="mb-7"><p className="eyebrow">Controlled market context</p><h2 className="page-title">Connect events to portfolio transmission.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-white/45">All series are rebased to 100 at 31 Dec 2025. Event descriptions come only from the supplied authoritative event log.</p></div>
              <article className="panel">
                <div className="panel-heading"><div><p className="panel-title">Market regime map</p><p className="panel-subtitle">Comparable indexed movements across five snapshots</p></div><span className="soft-label">31 Dec = 100</span></div>
                <ChartContainer config={Object.fromEntries(data.marketSeries.map((series, index) => [series.id, { label: series.name, color: CHART_COLORS[index] }]))} className="mt-5 h-[360px] w-full"><LineChart data={marketData} margin={{ top: 12, right: 12, bottom: 0, left: -15 }}><CartesianGrid vertical={false} stroke="rgba(255,255,255,.07)" /><XAxis dataKey="date" tickFormatter={chartDate} axisLine={false} tickLine={false} tickMargin={10} /><YAxis axisLine={false} tickLine={false} /><ChartTooltip content={<ChartTooltipContent indicator="line" />} />{data.marketSeries.map((series, index) => <Line key={series.id} type="monotone" dataKey={series.id} stroke={CHART_COLORS[index]} strokeWidth={2} dot={{ r: 3, fill: '#07100f', strokeWidth: 2 }} />)}</LineChart></ChartContainer>
                <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">{data.marketSeries.map((series, index) => <span key={series.id} className="flex items-center gap-2 text-[10px] text-white/42"><i className="h-2 w-2 rounded-full" style={{ background: CHART_COLORS[index] }} />{series.name}</span>)}</div>
              </article>

              <article className="panel mt-4">
                <div className="panel-heading"><div><p className="panel-title">Authoritative event timeline</p><p className="panel-subtitle">High and severe events only</p></div><ShieldCheck className="h-4 w-4 text-[#8ee5b5]" /></div>
                <div className="mt-6 grid gap-x-8 gap-y-0 lg:grid-cols-2">{data.events.map((event) => <div key={`${event.event_date}-${event.description}`} className="event-row"><div className={`event-dot ${event.severity === 'Severe' ? 'severe' : ''}`} /><div><div className="flex items-center gap-2"><span className="font-mono text-[10px] text-white/35">{event.event_date}</span><span className={`priority-pill ${event.severity === 'Severe' ? priorityStyles.Critical : priorityStyles.High}`}>{event.severity}</span></div><p className="mt-2 text-sm leading-5 text-white/68">{event.description}</p><p className="mt-2 text-[10px] leading-4 text-[#8ee5b5]/60">Transmission: {event.primary_transmission}</p></div></div>)}</div>
              </article>
            </section>
          )}

          {view === 'clients' && (
            <div className="fixed bottom-5 right-5 hidden w-[310px] xl:block">
              <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/28" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Quick switch client…" className="w-full rounded-full border border-white/10 bg-[#10211e]/95 py-3 pl-10 pr-4 text-xs text-white shadow-2xl outline-none backdrop-blur placeholder:text-white/25 focus:border-[#8ee5b5]/35" />{query && <div className="absolute bottom-[calc(100%+8px)] left-0 max-h-64 w-full overflow-auto rounded-2xl border border-white/10 bg-[#10211e] p-1.5 shadow-2xl">{filteredClients.map((client) => <button key={client.id} onClick={() => { setSelectedClientId(client.id); setQuery(''); }} className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-xs transition hover:bg-white/5"><span className="truncate">{client.name}</span><span className="text-white/28">{client.id}</span></button>)}</div>}</div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
