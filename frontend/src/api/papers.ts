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
  key_points: string[];
  citations: Citation[];
}

export interface Citation {
  [key: string]: unknown;
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
