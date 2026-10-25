import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';

import { getPaperSource } from '../api/papers';

interface SourcePassageDialogProps {
  paperId: string;
  chunkId: string;
  onClose: () => void;
}

function SourcePassageDialog({
  paperId,
  chunkId,
  onClose,
}: SourcePassageDialogProps) {
  const sourceQuery = useQuery({
    queryKey: ['paper-source', paperId, chunkId],
    queryFn: () => getPaperSource(paperId, chunkId),
  });

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-passage-title"
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-lg bg-white p-6 shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3
              id="source-passage-title"
              className="text-lg font-semibold text-slate-900"
            >
              Cited source passage
            </h3>
            {sourceQuery.data && (
              <p className="mt-1 text-sm text-slate-500">
                Page {sourceQuery.data.page} · {sourceQuery.data.section}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Close source passage"
            onClick={onClose}
            className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700"
          >
            <X size={18} />
          </button>
        </div>
        {sourceQuery.isLoading && (
          <p className="mt-5 text-sm text-slate-600">
            Loading the cited passage...
          </p>
        )}
        {sourceQuery.isError && (
          <p role="alert" className="mt-5 text-sm text-red-700">
            {sourceQuery.error instanceof Error
              ? sourceQuery.error.message
              : 'The cited passage could not be loaded.'}
          </p>
        )}
        {sourceQuery.data && (
          <blockquote className="mt-5 whitespace-pre-wrap border-l-4 border-blue-200 pl-4 text-sm leading-7 text-slate-800">
            {sourceQuery.data.text}
          </blockquote>
        )}
      </section>
    </div>
  );
}

export default SourcePassageDialog;
