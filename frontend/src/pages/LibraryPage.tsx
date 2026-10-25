
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Download,
  FileText,
  LoaderCircle,
  MessageCircle,
  Plus,
  RefreshCw,
  Search,
  Send,
} from 'lucide-react';

import {
  askPaperQuestion,
  createChatSession,
  exportPaperReport,
  getChatMessages,
  getPaper,
  getPaperStatus,
  getPaperSummary,
  listPapers,
  type Citation,
  type ChatMessage,
  type ReportFormat,
} from '../api/papers';

import UploadPaperModal from '../components/UploadPaperModal';
import SourcePassageDialog from '../components/SourcePassageDialog';

type Tab = 'summary' | 'details' | 'chat';

function readableCitationValue(citation: Citation): string {
  const preferredKeys = [
    'section',
    'page',
    'page_number',
    'text',
    'content',
    'chunk_text',
    'source',
  ];

  const parts = preferredKeys
    .filter((key) => citation[key] !== undefined && citation[key] !== null)
    .map((key) => {
      const value = citation[key];
      const label = key.replaceAll('_', ' ');

      if (typeof value === 'string' || typeof value === 'number') {
        return `${label}: ${String(value)}`;
      }

      return '';
    })
    .filter(Boolean);

  if (parts.length > 0) {
    return parts.join(' · ');
  }

  return (
    Object.entries(citation)
      .filter(
        ([, value]) =>
          typeof value === 'string' || typeof value === 'number',
      )
      .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${String(value)}`)
      .join(' · ') || 'Source reference available'
  );
}

function isUsefulText(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

function cleanKeyPoints(points: string[] | undefined): string[] {
  if (!Array.isArray(points)) {
    return [];
  }

  return points
    .filter(isUsefulText)
    .map((point) => point.trim())
    .filter((point) => {
      const normalized = point.toLowerCase();

      return (
        normalized !== 'not available' &&
        normalized !== 'n/a' &&
        normalized !== 'none'
      );
    });
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="text-base font-semibold text-slate-900">{title}</h3>
      <div className="mt-3 text-sm leading-7 text-slate-700">{children}</div>
    </section>
  );
}

function InformationField({
  label,
  value,
}: {
  label: string;
  value: string | number | null | undefined;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 break-words text-sm text-slate-800">
        {value === null || value === undefined || value === ''
          ? 'Not available in the extracted metadata'
          : value}
      </dd>
    </div>
  );
}

function CitationList({ citations }: { citations: Citation[] }) {
  const [selectedSource, setSelectedSource] = useState<{
    paperId: string;
    chunkId: string;
  } | null>(null);

  if (citations.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 border-t border-slate-200 pt-4">
      <h4 className="text-sm font-semibold text-slate-800">Sources</h4>

      <ol className="mt-3 space-y-2">
        {citations.map((citation, index) => (
          <li
            key={`${index}-${readableCitationValue(citation)}`}
            className="rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600"
          >
            {citation.paper_id && citation.chunk_id ? (
              <button
                type="button"
                onClick={() =>
                  setSelectedSource({
                    paperId: citation.paper_id!,
                    chunkId: citation.chunk_id!,
                  })
                }
                className="font-semibold text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700"
              >
                Source {index + 1}
                {citation.page ? ` · page ${citation.page}` : ''}
              </button>
            ) : (
              <span className="font-semibold text-slate-800">
                Source {index + 1}
              </span>
            )}
            <p className="mt-1 break-words">
              {readableCitationValue(citation)}
            </p>
          </li>
        ))}
      </ol>
      {selectedSource && (
        <SourcePassageDialog
          paperId={selectedSource.paperId}
          chunkId={selectedSource.chunkId}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </div>
  );
}

function LibraryPage() {
  const queryClient = useQueryClient();

  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('summary');
  const [searchTerm, setSearchTerm] = useState('');
  const [question, setQuestion] = useState('');
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [reportFormat, setReportFormat] = useState<ReportFormat | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['papers'],
    queryFn: listPapers,
  });

  const papers = data?.items ?? [];

  const selectedPaper =
    papers.find((paper) => paper.id === selectedPaperId) ?? null;

  const filteredPapers = papers.filter((paper) =>
    (paper.title ?? '')
      .toLowerCase()
      .includes(searchTerm.trim().toLowerCase()),
  );

  const detailsQuery = useQuery({
    queryKey: ['paper-details', selectedPaperId],
    queryFn: () => getPaper(selectedPaperId!),
    enabled: Boolean(selectedPaperId) && selectedPaper?.status === 'ready',
    retry: 1,
  });

  const summaryQuery = useQuery({
    queryKey: ['paper-summary', selectedPaperId],
    queryFn: () => getPaperSummary(selectedPaperId!),
    enabled: Boolean(selectedPaperId) && selectedPaper?.status === 'ready',
    retry: 1,
  });

  const statusQuery = useQuery({
    queryKey: ['paper-status', selectedPaperId],
    queryFn: () => getPaperStatus(selectedPaperId!),
    enabled: Boolean(selectedPaperId) && selectedPaper?.status !== 'ready',
    refetchInterval: (query) => {
      const status = query.state.data?.status;

      return status === 'ready' || status === 'failed' ? false : 3000;
    },
  });

  const messagesQuery = useQuery({
    queryKey: ['chat-messages', chatSessionId],
    queryFn: () => getChatMessages(chatSessionId!),
    enabled: Boolean(chatSessionId),
    retry: 1,
  });

  const createSessionMutation = useMutation({
    mutationFn: (paperId: string) => createChatSession(paperId),

    onSuccess: (result) => {
      setChatSessionId(result.session_id);
      setChatError(null);
    },

    onError: (mutationError: Error) => {
      setChatError(mutationError.message);
    },
  });

  // The session ID is passed directly into the mutation.
  // This avoids depending on React state updating before the request starts.
  const askQuestionMutation = useMutation({
    mutationFn: async ({
      sessionId,
      questionText,
    }: {
      sessionId: string;
      questionText: string;
    }) => {
      return askPaperQuestion(sessionId, questionText);
    },

    onSuccess: async (_result, variables) => {
      setQuestion('');
      setChatError(null);

      await queryClient.invalidateQueries({
        queryKey: ['chat-messages', variables.sessionId],
      });
    },

    onError: (mutationError: Error) => {
      setChatError(mutationError.message);
    },
  });

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    });
  }, [messagesQuery.data, askQuestionMutation.isPending]);

  function selectPaper(paper: (typeof papers)[number]) {
    if (paper.id === selectedPaperId) {
      return;
    }

    setSelectedPaperId(paper.id);
    setActiveTab('summary');
    setChatSessionId(null);
    setQuestion('');
    setChatError(null);
  }

  async function openChat() {
    setActiveTab('chat');

    if (
      !selectedPaperId ||
      chatSessionId ||
      createSessionMutation.isPending
    ) {
      return;
    }

    try {
      await createSessionMutation.mutateAsync(selectedPaperId);
    } catch {
      // The mutation displays the error in the interface.
    }
  }

  async function sendQuestion(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const trimmed = question.trim();

    if (
      !trimmed ||
      askQuestionMutation.isPending ||
      createSessionMutation.isPending
    ) {
      return;
    }

    if (!selectedPaperId) {
      setChatError('Select a paper before asking a question.');
      return;
    }

    setChatError(null);

    try {
      let sessionId = chatSessionId;

      // Create a session first if one does not exist.
      if (!sessionId) {
        const result =
          await createSessionMutation.mutateAsync(selectedPaperId);

        sessionId = result.session_id;
        setChatSessionId(sessionId);
      }

      // Use the local session ID immediately instead of waiting for
      // the chatSessionId state update to complete.
      await askQuestionMutation.mutateAsync({
        sessionId,
        questionText: trimmed,
      });
    } catch {
      // The relevant mutation displays the error in the interface.
    }
  }

  async function exportReport(format: ReportFormat) {
    if (!selectedPaperId || reportFormat) {
      return;
    }

    setReportFormat(format);
    setReportError(null);

    try {
      await exportPaperReport(selectedPaperId, format);
    } catch (exportError) {
      setReportError(
        exportError instanceof Error
          ? exportError.message
          : 'The report could not be generated.',
      );
    } finally {
      setReportFormat(null);
    }
  }

  const summary = summaryQuery.data;
  const keyPoints = cleanKeyPoints(summary?.key_points);
  const problem = summary?.problem ?? keyPoints[0];
  const approach = summary?.approach ?? keyPoints[1];
  const mainResult = summary?.main_result ?? keyPoints[2];
  const limitations = cleanKeyPoints(
    summary?.limitations ?? keyPoints.slice(3),
  );

  const messages: ChatMessage[] = messagesQuery.data?.items ?? [];

  const currentStatus =
    selectedPaper?.status === 'ready'
      ? 'ready'
      : statusQuery.data?.status ?? selectedPaper?.status ?? 'unknown';

  const processingError =
    statusQuery.data?.error ??
    (currentStatus === 'failed' ? 'Paper processing failed.' : null);

  return (
    <>
      <div className="flex min-h-screen bg-slate-50 text-slate-900">
        <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-5 py-5">
            <h1 className="text-base font-semibold">
              Research Paper Analyst
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Research workspace
            </p>
          </div>

          <div className="px-4 py-4">
            <button
              type="button"
              onClick={() => setUploadOpen(true)}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
            >
              <Plus size={16} />
              Upload paper
            </button>
          </div>

          <div className="px-4 pb-3">
            <div className="relative">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                type="search"
                placeholder="Search papers"
                aria-label="Search papers"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                className="w-full rounded-md border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:bg-white"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto px-3 pb-4">
            <div className="px-2 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                Library
              </p>
            </div>

            {isLoading && (
              <p className="px-4 py-6 text-center text-sm text-slate-500">
                Loading papers...
              </p>
            )}

            {isError && (
              <div className="px-4 py-6 text-center">
                <p className="text-sm text-red-600">
                  {error instanceof Error
                    ? error.message
                    : 'Could not load the paper library.'}
                </p>
                <button
                  type="button"
                  onClick={() => void refetch()}
                  className="mt-3 text-xs font-medium text-slate-700 underline underline-offset-2"
                >
                  Try again
                </button>
              </div>
            )}

            {!isLoading && !isError && filteredPapers.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-500">
                {papers.length === 0
                  ? 'No papers yet. Upload a paper to begin.'
                  : 'No papers match your search.'}
              </p>
            )}

            {!isLoading && !isError && filteredPapers.length > 0 && (
              <div className="space-y-1">
                {filteredPapers.map((paper) => {
                  const isSelected = paper.id === selectedPaperId;

                  return (
                    <button
                      key={paper.id}
                      type="button"
                      onClick={() => selectPaper(paper)}
                      aria-pressed={isSelected}
                      className={`w-full rounded-md px-3 py-3 text-left transition ${
                        isSelected
                          ? 'bg-slate-100 ring-1 ring-slate-200'
                          : 'hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <FileText
                          size={17}
                          className="mt-0.5 shrink-0 text-slate-400"
                        />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-800">
                            {paper.title}
                          </p>
                          <div className="mt-1 flex items-center gap-2">
                            {paper.year && (
                              <span className="text-xs text-slate-500">
                                {paper.year}
                              </span>
                            )}
                            <span className="text-xs text-slate-400">
                              {paper.status}
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 px-4 py-3">
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>Storage</span>
              <span>
                {papers.length} {papers.length === 1 ? 'paper' : 'papers'}
              </span>
            </div>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <header className="flex min-h-16 items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Library
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Analyze and explore your research papers
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Link
                to="/compare"
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Compare papers
              </Link>
              <button
                type="button"
                onClick={() => setUploadOpen(true)}
                className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                Add paper
              </button>
            </div>
          </header>

          <section className="mx-auto max-w-6xl px-6 py-8">
            {!selectedPaper ? (
              <div className="flex min-h-[520px] items-center justify-center">
                <div className="max-w-md text-center">
                  <div className="mx-auto mb-5 flex h-12 w-12 items-center justify-center rounded-md border border-slate-200 bg-white">
                    <BookOpen size={22} className="text-slate-400" />
                  </div>
                  <h3 className="text-lg font-semibold">
                    Select a paper to begin
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Choose a paper from your library to open its workspace.
                  </p>
                  <button
                    type="button"
                    onClick={() => setUploadOpen(true)}
                    className="mt-6 inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
                  >
                    <Plus size={16} />
                    Upload your first paper
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <h2 className="break-words text-xl font-semibold">
                        {detailsQuery.data?.title || selectedPaper.title}
                      </h2>
                      <p className="mt-2 text-sm text-slate-500">
                        Status: {currentStatus}
                        {selectedPaper.year ? ` · ${selectedPaper.year}` : ''}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          void summaryQuery.refetch();
                          void detailsQuery.refetch();
                          void queryClient.invalidateQueries({
                            queryKey: ['papers'],
                          });
                        }}
                        className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      >
                        <RefreshCw size={14} />
                        Refresh
                      </button>
                      {(['pdf', 'md'] as const).map((format) => (
                        <button
                          key={format}
                          type="button"
                          onClick={() => void exportReport(format)}
                          disabled={
                            currentStatus !== 'ready' ||
                            reportFormat !== null
                          }
                          className="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Download size={14} />
                          {reportFormat === format
                            ? `Generating ${format.toUpperCase()}...`
                            : `Export ${format.toUpperCase()}`}
                        </button>
                      ))}
                    </div>
                  </div>
                  {reportError && (
                    <p
                      role="alert"
                      className="mt-3 text-sm text-red-700"
                    >
                      {reportError}
                    </p>
                  )}
                </div>

                <nav
                  className="flex gap-6 border-b border-slate-200"
                  aria-label="Research workspace sections"
                >
                  {(
                    [
                      ['summary', 'Summary'],
                      ['details', 'Details'],
                      ['chat', 'Chat'],
                    ] as [Tab, string][]
                  ).map(([tab, label]) => (
                    <button
                      key={tab}
                      type="button"
                      onClick={() => {
                        if (tab === 'chat') {
                          void openChat();
                        } else {
                          setActiveTab(tab);
                        }
                      }}
                      aria-current={
                        activeTab === tab ? 'page' : undefined
                      }
                      className={`border-b-2 pb-3 text-sm font-medium transition ${
                        activeTab === tab
                          ? 'border-slate-900 text-slate-900'
                          : 'border-transparent text-slate-500 hover:text-slate-800'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </nav>

                <div className="space-y-5 py-6">
                  {currentStatus !== 'ready' && (
                    <div className="rounded-lg border border-slate-200 bg-white p-5">
                      <div className="flex items-start gap-3">
                        {currentStatus === 'failed' ? (
                          <AlertCircle
                            className="mt-0.5 text-red-600"
                            size={20}
                          />
                        ) : (
                          <LoaderCircle
                            className="mt-0.5 animate-spin text-slate-500"
                            size={20}
                          />
                        )}
                        <div>
                          <h3 className="font-semibold">
                            {currentStatus === 'failed'
                              ? 'Paper processing failed'
                              : 'Analyzing your paper'}
                          </h3>
                          <p className="mt-1 text-sm leading-6 text-slate-600">
                            {processingError ||
                              statusQuery.data?.stage ||
                              'Please wait while the paper is processed.'}
                          </p>
                          {statusQuery.data &&
                            currentStatus !== 'failed' && (
                              <p className="mt-2 text-xs text-slate-500">
                                Progress: {statusQuery.data.progress}%
                              </p>
                            )}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'summary' && currentStatus === 'ready' && (
                    <>
                      {summaryQuery.isLoading && (
                        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-500">
                          <LoaderCircle
                            size={18}
                            className="mr-2 inline animate-spin"
                          />
                          Loading the generated analysis...
                        </div>
                      )}

                      {summaryQuery.isError && (
                        <div className="rounded-lg border border-red-200 bg-white p-5">
                          <p className="text-sm text-red-700">
                            {summaryQuery.error instanceof Error
                              ? summaryQuery.error.message
                              : 'The summary could not be loaded.'}
                          </p>
                          <button
                            type="button"
                            onClick={() => void summaryQuery.refetch()}
                            className="mt-3 text-sm underline"
                          >
                            Try again
                          </button>
                        </div>
                      )}

                      {summary && (
                        <>
                          <SectionCard title="Executive summary">
                            {isUsefulText(summary.summary)
                              ? summary.summary
                              : 'A summary was not generated. Refresh the analysis or check the backend logs.'}
                          </SectionCard>

                          <SectionCard title="Problem statement">
                            {problem ??
                              'The research problem was not available in the generated analysis.'}
                          </SectionCard>

                          <SectionCard title="Methodology and approach">
                            {approach ??
                              'The methodology was not available in the generated analysis.'}
                          </SectionCard>

                          <SectionCard title="Main result">
                            {mainResult ??
                              'The main result was not available in the generated analysis.'}
                          </SectionCard>

                          <SectionCard title="Reported limitations">
                            {limitations.length > 0 ? (
                              <ul className="list-disc space-y-2 pl-5">
                                {limitations.map((limitation, index) => (
                                  <li key={`${index}-${limitation}`}>
                                    {limitation}
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-slate-500">
                                No limitations were returned in the generated
                                analysis.
                              </p>
                            )}
                          </SectionCard>

                          <div className="rounded-lg border border-slate-200 bg-white p-5">
                            <div className="flex items-center gap-2">
                              <CheckCircle2
                                size={18}
                                className="text-slate-500"
                              />
                              <h3 className="font-semibold">
                                Analysis status
                              </h3>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-slate-600">
                              The paper has been indexed for retrieval. Ask a
                              question in the Chat tab to explore specific
                              claims and source passages.
                            </p>
                          </div>
                        </>
                      )}
                    </>
                  )}

                  {activeTab === 'details' && (
                    <>
                      {detailsQuery.isLoading && (
                        <div className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-500">
                          Loading paper metadata...
                        </div>
                      )}

                      {detailsQuery.isError && (
                        <div className="rounded-lg border border-red-200 bg-white p-5 text-sm text-red-700">
                          {detailsQuery.error instanceof Error
                            ? detailsQuery.error.message
                            : 'Paper details could not be loaded.'}
                        </div>
                      )}

                      {detailsQuery.data && (
                        <SectionCard title="Publication metadata">
                          <dl className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
                            <InformationField
                              label="Title"
                              value={detailsQuery.data.title}
                            />
                            <InformationField
                              label="Authors"
                              value={
                                detailsQuery.data.authors.length
                                  ? detailsQuery.data.authors.join(', ')
                                  : null
                              }
                            />
                            <InformationField
                              label="Publication venue"
                              value={detailsQuery.data.venue}
                            />
                            <InformationField
                              label="Publication year"
                              value={detailsQuery.data.year}
                            />
                            <InformationField
                              label="DOI"
                              value={detailsQuery.data.doi}
                            />
                            <InformationField
                              label="arXiv ID"
                              value={detailsQuery.data.arxiv_id}
                            />
                            <InformationField
                              label="Processing status"
                              value={detailsQuery.data.status}
                            />
                            <InformationField
                              label="Paper ID"
                              value={detailsQuery.data.id}
                            />
                          </dl>
                        </SectionCard>
                      )}

                      <SectionCard title="Indexing and analysis">
                        <p>
                          The backend extracts PDF text, detects sections,
                          creates embeddings, and indexes searchable chunks for
                          retrieval-based question answering.
                        </p>
                      </SectionCard>
                    </>
                  )}

                  {activeTab === 'chat' && (
                    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                      <div className="border-b border-slate-200 px-5 py-4">
                        <div className="flex items-center gap-2">
                          <MessageCircle size={19} />
                          <h3 className="font-semibold">
                            Chat with this paper
                          </h3>
                        </div>
                        <p className="mt-1 text-sm text-slate-500">
                          Ask questions about the paper. Answers use retrieved
                          paper passages when relevant evidence is available.
                        </p>
                      </div>

                      <div className="max-h-[480px] min-h-[260px] space-y-4 overflow-y-auto p-5">
                        {createSessionMutation.isPending && (
                          <p className="text-sm text-slate-500">
                            Preparing your chat session...
                          </p>
                        )}

                        {messagesQuery.isLoading && chatSessionId && (
                          <p className="text-sm text-slate-500">
                            Loading conversation...
                          </p>
                        )}

                        {messagesQuery.isError && (
                          <p className="text-sm text-red-600">
                            Chat history could not be loaded. Try reopening
                            the Chat tab.
                          </p>
                        )}

                        {!createSessionMutation.isPending &&
                          !messagesQuery.isLoading &&
                          messages.length === 0 && (
                            <div className="py-8 text-center">
                              <MessageCircle
                                size={28}
                                className="mx-auto text-slate-300"
                              />
                              <p className="mt-3 text-sm font-medium text-slate-700">
                                Start a conversation
                              </p>
                              <p className="mt-1 text-sm text-slate-500">
                                Try asking: “What is the main problem addressed
                                in this paper?”
                              </p>
                            </div>
                          )}

                        {messages.map((message) => (
                          <div
                            key={message.id}
                            className={`flex ${
                              message.role === 'user'
                                ? 'justify-end'
                                : 'justify-start'
                            }`}
                          >
                            <div
                              className={`max-w-[90%] rounded-lg px-4 py-3 ${
                                message.role === 'user'
                                  ? 'bg-slate-900 text-white'
                                  : 'bg-slate-100 text-slate-800'
                              }`}
                            >
                              <p className="whitespace-pre-wrap break-words text-sm leading-6">
                                {message.content}
                              </p>

                              {message.role !== 'user' && (
                                <div className="text-slate-700">
                                  <CitationList
                                    citations={message.citations ?? []}
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                        ))}

                        {askQuestionMutation.isPending && (
                          <div className="flex items-center gap-2 text-sm text-slate-500">
                            <LoaderCircle
                              size={16}
                              className="animate-spin"
                            />
                            Analyzing the paper passages...
                          </div>
                        )}

                        <div ref={chatEndRef} />
                      </div>

                      {chatError && (
                        <div className="mx-5 mb-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                          {chatError}
                        </div>
                      )}

                      <form
                        onSubmit={sendQuestion}
                        className="flex items-end gap-3 border-t border-slate-200 p-4"
                      >
                        <textarea
                          value={question}
                          onChange={(event) => setQuestion(event.target.value)}
                          onKeyDown={(event) => {
                            if (
                              event.key === 'Enter' &&
                              !event.shiftKey
                            ) {
                              event.preventDefault();
                              event.currentTarget.form?.requestSubmit();
                            }
                          }}
                          placeholder="Ask a question about this paper..."
                          aria-label="Question about the paper"
                          rows={2}
                          className="min-h-12 flex-1 resize-y rounded-md border border-slate-200 px-3 py-2 text-sm outline-none focus:border-slate-400"
                        />

                        <button
                          type="submit"
                          disabled={
                            !question.trim() ||
                            askQuestionMutation.isPending ||
                            createSessionMutation.isPending
                          }
                          className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {askQuestionMutation.isPending ? (
                            <LoaderCircle
                              size={16}
                              className="animate-spin"
                            />
                          ) : (
                            <Send size={16} />
                          )}
                          Send
                        </button>
                      </form>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        </main>
      </div>

      <UploadPaperModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => {
          void queryClient.invalidateQueries({
            queryKey: ['papers'],
          });
          void refetch();
        }}
      />
    </>
  );
}

export default LibraryPage;
