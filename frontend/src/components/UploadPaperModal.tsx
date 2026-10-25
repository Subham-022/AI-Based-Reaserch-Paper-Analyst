import { useState } from 'react';
import { FileText, Link, Loader2, Upload, X } from 'lucide-react';

import {
  uploadPaper,
  uploadPaperFromUrl,
} from '../api/papers';

type UploadMode = 'file' | 'url';

interface UploadPaperModalProps {
  open: boolean;
  onClose: () => void;
  onUploaded?: () => void;
}

function UploadPaperModal({
  open,
  onClose,
  onUploaded,
}: UploadPaperModalProps) {
  const [mode, setMode] = useState<UploadMode>('file');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  if (!open) {
    return null;
  }

  const handleFileChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const selectedFile = event.target.files?.[0] ?? null;

    setError('');

    if (!selectedFile) {
      setFile(null);
      return;
    }

    if (
      selectedFile.type !== 'application/pdf' &&
      !selectedFile.name.toLowerCase().endsWith('.pdf')
    ) {
      setFile(null);
      setError('Please select a PDF file.');
      return;
    }

    setFile(selectedFile);
  };

  const handleUpload = async () => {
    if (uploading) {
      return;
    }

    if (mode === 'file') {
      if (!file) {
        return;
      }

      setUploading(true);
      setError('');

      try {
        await uploadPaper(file);

        setFile(null);
        setUrl('');
        onUploaded?.();
        onClose();
      } catch (uploadError) {
        const message =
          uploadError instanceof Error
            ? uploadError.message
            : 'The paper could not be uploaded.';

        setError(message);
      } finally {
        setUploading(false);
      }

      return;
    }

    const trimmedUrl = url.trim();

    if (!trimmedUrl) {
      setError('Please enter a paper URL.');
      return;
    }

    setUploading(true);
    setError('');

    try {
      await uploadPaperFromUrl(trimmedUrl);

      setFile(null);
      setUrl('');
      onUploaded?.();
      onClose();
    } catch (uploadError) {
      const message =
        uploadError instanceof Error
          ? uploadError.message
          : 'The paper URL could not be processed.';

      setError(message);
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    if (uploading) {
      return;
    }

    setError('');
    setFile(null);
    setUrl('');
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-paper-title"
    >
      <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <h2
              id="upload-paper-title"
              className="text-base font-semibold text-slate-900"
            >
              Add research paper
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Upload a PDF or provide a paper URL.
            </p>
          </div>

          <button
            type="button"
            onClick={handleClose}
            disabled={uploading}
            aria-label="Close upload dialog"
            className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <X size={18} />
          </button>
        </div>

        <div className="border-b border-slate-200 px-6">
          <div className="flex gap-6">
            <button
              type="button"
              onClick={() => {
                setMode('file');
                setError('');
              }}
              disabled={uploading}
              className={`border-b-2 py-3 text-sm font-medium ${
                mode === 'file'
                  ? 'border-slate-900 text-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Upload PDF
            </button>

            <button
              type="button"
              onClick={() => {
                setMode('url');
                setError('');
              }}
              disabled={uploading}
              className={`border-b-2 py-3 text-sm font-medium ${
                mode === 'url'
                  ? 'border-slate-900 text-slate-900'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              Paper URL
            </button>
          </div>
        </div>

        <div className="px-6 py-6">
          {mode === 'file' ? (
            <div>
              <label
                htmlFor="paper-file"
                className="flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 px-6 text-center transition hover:border-slate-400 hover:bg-slate-100"
              >
                <Upload size={24} className="text-slate-400" />

                <span className="mt-3 text-sm font-medium text-slate-800">
                  Select a research paper
                </span>

                <span className="mt-1 text-xs text-slate-500">
                  PDF files only
                </span>

                {file ? (
                  <div className="mt-4 flex max-w-full items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2">
                    <FileText
                      size={15}
                      className="shrink-0 text-slate-500"
                    />

                    <span
                      className="max-w-xs truncate text-xs font-medium text-slate-700"
                      title={file.name}
                    >
                      {file.name}
                    </span>
                  </div>
                ) : null}
              </label>

              <input
                id="paper-file"
                type="file"
                accept="application/pdf,.pdf"
                onChange={handleFileChange}
                disabled={uploading}
                className="sr-only"
              />

              {file && (
                <p className="mt-2 text-xs text-slate-500">
                  Selected: {file.name}
                </p>
              )}
            </div>
          ) : (
            <div>
              <label
                htmlFor="paper-url"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                Research paper URL
              </label>

              <div className="relative">
                <Link
                  size={17}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />

                <input
                  id="paper-url"
                  type="url"
                  value={url}
                  onChange={(event) => {
                    setUrl(event.target.value);
                    setError('');
                  }}
                  disabled={uploading}
                  placeholder="https://arxiv.org/..."
                  className="w-full rounded-md border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-100 disabled:bg-slate-50"
                />
              </div>

              <p className="mt-2 text-xs leading-5 text-slate-500">
                Supports arXiv, DOI, and direct PDF URLs.
              </p>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700"
            >
              {error}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
          <button
            type="button"
            onClick={handleClose}
            disabled={uploading}
            className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleUpload}
            disabled={
              (mode === 'file' && !file) ||
              (mode === 'url' && !url.trim()) ||
              uploading
            }
            className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {uploading && (
              <Loader2
                size={15}
                className="animate-spin"
              />
            )}

            {uploading
              ? 'Uploading...'
              : mode === 'file'
                ? 'Add paper'
                : 'Fetch paper'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default UploadPaperModal;