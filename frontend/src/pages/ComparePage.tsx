import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, LoaderCircle, Scale } from 'lucide-react';
import { Link } from 'react-router-dom';

import {
  comparePapers,
  listPapers,
  type ComparisonRow,
} from '../api/papers';
import SourcePassageDialog from '../components/SourcePassageDialog';

function ComparePage() {
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectedSource, setSelectedSource] = useState<{
    paperId: string;
    chunkId: string;
  } | null>(null);
  const papersQuery = useQuery({
    queryKey: ['papers'],
    queryFn: listPapers,
  });
  const compareMutation = useMutation({
    mutationFn: comparePapers,
  });
  const readyPapers = (papersQuery.data?.items ?? []).filter(
    (paper) => paper.status === 'ready',
  );

  function togglePaper(paperId: string) {
    setSelectedIds((current) =>
      current.includes(paperId)
        ? current.filter((id) => id !== paperId)
        : [...current, paperId],
    );
  }

  const comparison = compareMutation.data;

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Compare papers</h1>
            <p className="mt-1 text-sm text-slate-500">
              Compare retrieved evidence with source pages side by side.
            </p>
          </div>
          <Link
            to="/library"
            className="inline-flex items-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-950"
          >
            <ArrowLeft size={16} />
            Back to library
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-6xl space-y-6 px-6 py-8">
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="font-semibold">Select papers</h2>
          <p className="mt-1 text-sm text-slate-500">
            Choose at least two ready papers. Cells show retrieved passages;
            dimensions without matching evidence are marked as not reported.
          </p>

          {papersQuery.isLoading && (
            <p className="mt-4 text-sm text-slate-500">Loading papers...</p>
          )}
          {papersQuery.isError && (
            <p role="alert" className="mt-4 text-sm text-red-700">
              {papersQuery.error instanceof Error
                ? papersQuery.error.message
                : 'The paper library could not be loaded.'}
            </p>
          )}
          {!papersQuery.isLoading &&
            !papersQuery.isError &&
            readyPapers.length === 0 && (
              <p className="mt-4 text-sm text-slate-500">
                No ready papers are available to compare.
              </p>
            )}

          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {readyPapers.map((paper) => (
              <label
                key={paper.id}
                className="flex cursor-pointer items-start gap-3 rounded-md border border-slate-200 p-3 hover:bg-slate-50"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.includes(paper.id)}
                  onChange={() => togglePaper(paper.id)}
                  className="mt-1"
                />
                <span className="min-w-0">
                  <span className="block break-words text-sm font-medium">
                    {paper.title}
                  </span>
                  <span className="mt-1 block text-xs text-slate-500">
                    Ready
                  </span>
                </span>
              </label>
            ))}
          </div>

          <button
            type="button"
            onClick={() => compareMutation.mutate(selectedIds)}
            disabled={selectedIds.length < 2 || compareMutation.isPending}
            className="mt-5 inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {compareMutation.isPending ? (
              <LoaderCircle size={16} className="animate-spin" />
            ) : (
              <Scale size={16} />
            )}
            {compareMutation.isPending ? 'Comparing...' : 'Compare selected'}
          </button>
          {compareMutation.isError && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              {compareMutation.error instanceof Error
                ? compareMutation.error.message
                : 'The selected papers could not be compared.'}
            </p>
          )}
        </div>

        {comparison && (
          <ComparisonTable
            rows={comparison.rows}
            papers={comparison.papers}
            onSourceClick={setSelectedSource}
          />
        )}
      </section>
      {selectedSource && (
        <SourcePassageDialog
          paperId={selectedSource.paperId}
          chunkId={selectedSource.chunkId}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </main>
  );
}

function ComparisonTable({
  rows,
  papers,
  onSourceClick,
}: {
  rows: ComparisonRow[];
  papers: Array<{ id: string; title: string }>;
  onSourceClick: (source: { paperId: string; chunkId: string }) => void;
}) {
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-slate-200 bg-white p-5 text-sm text-slate-600">
        The comparison returned no dimensions.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-100">
          <tr>
            <th className="px-4 py-3 font-semibold">Dimension</th>
            {papers.map((paper) => (
              <th key={paper.id} className="min-w-64 px-4 py-3 font-semibold">
                {paper.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {rows.map((row) => (
            <tr key={row.dimension} className="align-top">
              <th className="whitespace-nowrap px-4 py-4 font-medium capitalize">
                {row.dimension}
              </th>
              {papers.map((paper) => {
                const cell = row.cells.find(
                  (candidate) => candidate.paper_id === paper.id,
                );

                return (
                  <td key={paper.id} className="px-4 py-4">
                    <p className="whitespace-pre-wrap leading-6 text-slate-700">
                      {cell?.value || 'Not reported in retrieved evidence.'}
                    </p>
                    {cell?.citations.length ? (
                      <ul className="mt-3 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-500">
                        {cell.citations.map((citation, index) => (
                          <li key={`${citation.chunk_id}-${index}`}>
                            <button
                              type="button"
                              onClick={() =>
                                onSourceClick({
                                  paperId: citation.paper_id,
                                  chunkId: citation.chunk_id,
                                })
                              }
                              className="text-blue-700 underline decoration-blue-300 underline-offset-2 hover:text-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700"
                            >
                              Source p. {citation.page} · {citation.section}
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ComparePage;
