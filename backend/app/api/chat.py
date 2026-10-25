
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.config import (
    CHROMA_DIR,
    EMBEDDING_MODEL,
    RETRIEVAL_MIN_SCORE,
)
from app.db import get_session
from app.models import (
    ChatMessage,
    ChatSession,
    ChatSessionPaper,
    Paper,
    utc_now,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


class SessionRequest(BaseModel):
    paper_ids: list[str] = Field(min_length=1)
    title: str | None = None


class QuestionRequest(BaseModel):
    session_id: str
    question: str
    section: str | None = None


def _error(
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


def _get_llm():
    from app.config import (
        LLM_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL,
        LLM_PROVIDER,
        OLLAMA_BASE_URL,
    )

    if LLM_PROVIDER == "ollama":
        from app.llm.ollama_client import OllamaClient

        return OllamaClient(
            base_url=OLLAMA_BASE_URL,
            model=LLM_MODEL,
        )

    if LLM_PROVIDER == "anthropic":
        from app.llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            api_key=LLM_API_KEY,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
        )

    if LLM_PROVIDER == "openai-compatible":
        from app.llm.openai_client import (
            OpenAICompatibleClient,
        )

        return OpenAICompatibleClient(
            api_key=LLM_API_KEY,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
        )

    raise RuntimeError(
        f"Unsupported LLM provider: {LLM_PROVIDER}"
    )


def _get_retriever():
    """Open the existing persistent vector index for paper retrieval."""
    from app.retrieval.embedder import Embedder
    from app.retrieval.search import Retriever
    from app.retrieval.store import VectorStore

    embedder = Embedder(
        model_name=EMBEDDING_MODEL
    )
    store = VectorStore(
        CHROMA_DIR
    )

    return Retriever(
        store=store,
        embedder=embedder,
        confidence_threshold=RETRIEVAL_MIN_SCORE,
    )


@router.post("/sessions")
def create_session(
    request: SessionRequest,
    session: Session = Depends(get_session),
) -> dict:
    papers = []

    for paper_id in request.paper_ids:
        paper = session.get(Paper, paper_id)

        if paper is None:
            raise _error(
                404,
                "PAPER_NOT_FOUND",
                f"Paper {paper_id} does not exist.",
            )

        if paper.status != "ready":
            raise _error(
                409,
                "PAPER_NOT_READY",
                f"Paper {paper_id} is not ready.",
            )

        papers.append(paper)

    chat_session = ChatSession(
        id=uuid.uuid4().hex,
        title=request.title,
    )
    session.add(chat_session)

    for paper in papers:
        session.add(
            ChatSessionPaper(
                session_id=chat_session.id,
                paper_id=paper.id,
            )
        )

    session.commit()

    return {
        "session_id": chat_session.id,
        "paper_ids": [
            paper.id for paper in papers
        ],
    }


@router.get("/sessions/{session_id}/messages")
def messages(
    session_id: str,
    session: Session = Depends(get_session),
) -> dict:
    chat_session = session.get(
        ChatSession,
        session_id,
    )

    if chat_session is None:
        raise _error(
            404,
            "SESSION_NOT_FOUND",
            "The requested chat session does not exist.",
        )

    rows = session.exec(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id
        )
        .order_by(ChatMessage.created_at)
    ).all()

    return {
        "items": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "citations": json.loads(
                    item.citations_json or "[]"
                ),
            }
            for item in rows
        ]
    }


@router.post("/questions")
def ask_question(
    request: QuestionRequest,
    session: Session = Depends(get_session),
) -> dict:
    if not request.question.strip():
        raise _error(
            400,
            "INVALID_QUESTION",
            "The question cannot be empty.",
        )

    chat_session = session.get(
        ChatSession,
        request.session_id,
    )

    if chat_session is None:
        raise _error(
            404,
            "SESSION_NOT_FOUND",
            "The requested chat session does not exist.",
        )

    paper_links = session.exec(
        select(ChatSessionPaper).where(
            ChatSessionPaper.session_id
            == request.session_id
        )
    ).all()

    paper_ids = [
        item.paper_id for item in paper_links
    ]

    if not paper_ids:
        return {
            "answer": "not found in the provided papers",
            "citations": [],
            "found": False,
        }

    for paper_id in paper_ids:
        paper = session.get(Paper, paper_id)

        if paper is None:
            raise _error(
                404,
                "PAPER_NOT_FOUND",
                "A paper in this session no longer exists.",
            )

        if paper.status != "ready":
            raise _error(
                409,
                "PAPER_NOT_READY",
                "A paper in this session is still processing.",
            )

    stage = "retriever initialization"

    try:
        logger.info(
            "Chat question started: session=%s, papers=%s",
            request.session_id,
            len(paper_ids),
        )

        retriever = _get_retriever()

        stage = "retrieval"

        citations = retriever.search(
            query=request.question,
            paper_ids=paper_ids,
            section=request.section,
        )

        logger.info(
            "Chat retrieval completed: session=%s, passages=%s",
            request.session_id,
            len(citations),
        )

        if not citations:
            return _save_answer(
                session,
                request.session_id,
                request.question,
                {
                    "answer": "not found in the provided papers",
                    "citations": [],
                    "found": False,
                },
            )

        best_score = max(
            float(item.score)
            for item in citations
        )

        logger.info(
            "Chat retrieval score: session=%s, best_score=%.4f, threshold=%.4f",
            request.session_id,
            best_score,
            RETRIEVAL_MIN_SCORE,
        )

        if best_score < RETRIEVAL_MIN_SCORE:
            return _save_answer(
                session,
                request.session_id,
                request.question,
                {
                    "answer": "not found in the provided papers",
                    "citations": [],
                    "found": False,
                },
            )

        stage = "LLM initialization"
        llm = _get_llm()

        stage = "answer generation"

        from app.analysis.qa import answer_question

        result = answer_question(
            llm,
            request.question,
            citations,
        )

        citation_data = [
            citation.model_dump()
            for citation in result.citations
        ]

        response = {
            "answer": result.answer,
            "citations": citation_data,
            "found": bool(citation_data),
        }

        stage = "saving chat messages"

        return _save_answer(
            session,
            request.session_id,
            request.question,
            response,
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Chat question failed at stage '%s' "
            "(session=%s, paper_count=%d)",
            stage,
            request.session_id,
            len(paper_ids),
        )

        raise _error(
            502,
            "ANALYSIS_FAILED",
            "The question could not be answered.",
        ) from None


def _save_answer(
    session: Session,
    session_id: str,
    question: str,
    response: dict,
) -> dict:
    user_message = ChatMessage(
        id=uuid.uuid4().hex,
        session_id=session_id,
        role="user",
        content=question,
        citations_json="[]",
    )

    assistant_message = ChatMessage(
        id=uuid.uuid4().hex,
        session_id=session_id,
        role="assistant",
        content=response["answer"],
        citations_json=json.dumps(
            response["citations"]
        ),
    )

    chat_session = session.get(
        ChatSession,
        session_id,
    )

    if chat_session:
        chat_session.updated_at = utc_now()
        session.add(chat_session)

    session.add(user_message)
    session.add(assistant_message)
    session.commit()

    return response
