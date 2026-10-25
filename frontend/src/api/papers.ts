const API_BASE_URL = 'http://localhost:8000/api';

export interface Paper {
  id: string;
  title: string;
  year: number | null;
  status: string;
}

export interface PaperListResponse {
  items: Paper[];
}

export interface UploadPaperResponse {
  paper_id: string;
  job_id: string;
  status: string;
}

export interface PaperDetails {
  id: string;
  title: string | null;
  authors: string[];
  venue: string | null;
  year: number | null;
  doi: string | null;
  arxiv_id: string | null;
  status: string;
}

export interface PaperSummary {
  paper_id: string;
  summary: string;
  problem?: string;
  approach?: string;
  main_result?: string;
  limitations?: string[];
  key_points: string[];
  citations: Citation[];
}

export interface Citation {
  paper_id?: string;
  chunk_id?: string;
  page?: number;
  section?: string;
  [key: string]: unknown;
}

export interface SourcePassage {
  paper_id: string;
  chunk_id: string;
  page: number;
  section: string;
  text: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | string;
  content: string;
  citations: Citation[];
}

export interface ChatSessionResponse {
  session_id: string;
  paper_ids: string[];
}

export interface ChatMessagesResponse {
  items: ChatMessage[];
}

export interface ChatAnswerResponse {
  answer: string;
  citations: Citation[];
  found: boolean;
}

export interface PaperStatus {
  paper_id: string;
  status: string;
  progress: number;
  stage: string | null;
  error: string | null;
}

export type ReportFormat = 'md' | 'pdf';

export interface ComparisonCell {
  paper_id: string;
  value: string;
  citations: Array<{
    paper_id: string;
    chunk_id: string;
    page: number;
    section: string;
  }>;
}

export interface ComparisonRow {
  dimension: string;
  cells: ComparisonCell[];
}

export interface PaperComparisonResponse {
  papers: Array<{ id: string; title: string }>;
  rows: ComparisonRow[];
  charts: string[];
}

async function getErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const data: unknown = await response.json();

    if (typeof data === 'object' && data !== null && 'detail' in data) {
      const detail = data.detail;

      if (typeof detail === 'string') {
        return detail;
      }

      if (typeof detail === 'object' && detail !== null && 'error' in detail) {
        const error = detail.error;

        if (
          typeof error === 'object' &&
          error !== null &&
          'message' in error &&
          typeof error.message === 'string'
        ) {
          return error.message;
        }
      }
    }
  } catch {
    // The server may not return JSON.
  }

  return fallback;
}

async function request<T>(
  path: string,
  init?: RequestInit,
  fallback = 'The request could not be completed.',
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new Error(
      'Cannot connect to the backend. Make sure the FastAPI server is running.',
    );
  }

  if (!response.ok) {
    throw new Error(await getErrorMessage(response, fallback));
  }

  return response.json() as Promise<T>;
}

export async function uploadPaper(
  file: File,
): Promise<UploadPaperResponse> {
  const formData = new FormData();
  formData.append('file', file);

  return request<UploadPaperResponse>(
    '/papers/upload',
    {
      method: 'POST',
      body: formData,
    },
    'The paper could not be uploaded.',
  );
}

export async function uploadPaperFromUrl(
  url: string,
): Promise<UploadPaperResponse> {
  return request<UploadPaperResponse>(
    '/papers/url',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url }),
    },
    'The paper URL could not be processed.',
  );
}

export async function listPapers(): Promise<PaperListResponse> {
  return request<PaperListResponse>(
    '/papers',
    undefined,
    'The paper library could not be loaded.',
  );
}

export async function getPaper(
  paperId: string,
): Promise<PaperDetails> {
  return request<PaperDetails>(
    `/papers/${encodeURIComponent(paperId)}`,
    undefined,
    'Paper details could not be loaded.',
  );
}

export async function getPaperSummary(
  paperId: string,
): Promise<PaperSummary> {
  return request<PaperSummary>(
    `/papers/${encodeURIComponent(paperId)}/summary`,
    undefined,
    'The paper summary could not be loaded.',
  );
}

export async function getPaperSource(
  paperId: string,
  chunkId: string,
): Promise<SourcePassage> {
  return request<SourcePassage>(
    `/papers/${encodeURIComponent(paperId)}/source/${encodeURIComponent(chunkId)}`,
    undefined,
    'The cited source passage could not be loaded.',
  );
}

export async function getPaperStatus(
  paperId: string,
): Promise<PaperStatus> {
  return request<PaperStatus>(
    `/papers/${encodeURIComponent(paperId)}/status`,
    undefined,
    'Paper processing status could not be loaded.',
  );
}

export async function createChatSession(
  paperId: string,
): Promise<ChatSessionResponse> {
  return request<ChatSessionResponse>(
    '/chat/sessions',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        paper_ids: [paperId],
        title: 'Research paper discussion',
      }),
    },
    'A chat session could not be created.',
  );
}

export async function getChatMessages(
  sessionId: string,
): Promise<ChatMessagesResponse> {
  return request<ChatMessagesResponse>(
    `/chat/sessions/${encodeURIComponent(sessionId)}/messages`,
    undefined,
    'Chat history could not be loaded.',
  );
}

export async function askPaperQuestion(
  sessionId: string,
  question: string,
): Promise<ChatAnswerResponse> {
  return request<ChatAnswerResponse>(
    '/chat/questions',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        question,
      }),
    },
    'The question could not be answered.',
  );
}

export async function exportPaperReport(
  paperId: string,
  format: ReportFormat,
): Promise<void> {
  const report = await request<{ download_url: string }>(
    '/reports',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        paper_ids: [paperId],
        format,
      }),
    },
    'The report could not be generated.',
  );

  let response: Response;

  try {
    response = await fetch(
      new URL(report.download_url, API_BASE_URL),
    );
  } catch {
    throw new Error('The generated report could not be downloaded.');
  }

  if (!response.ok) {
    throw new Error(
      await getErrorMessage(
        response,
        'The generated report could not be downloaded.',
      ),
    );
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `research-paper-report.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

export async function comparePapers(
  paperIds: string[],
): Promise<PaperComparisonResponse> {
  return request<PaperComparisonResponse>(
    '/compare',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ paper_ids: paperIds }),
    },
    'The selected papers could not be compared.',
  );
}
