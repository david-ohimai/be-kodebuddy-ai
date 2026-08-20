"""
Local demo harness for Dev B's retrieval tools.

Owner: Dev B (Retrieval & Tools)

THIS IS NOT THE PRODUCTION LLM CLIENT. Dev D owns `app/agent/service.py` and
the real request path; Dev C owns the LangGraph orchestration. This script
exists so the retrieval tools can be exercised end to end — real DB, real RBAC
scoping, real tool calls — and so the final grounded answer can be inspected on
stdout without waiting for the graph or the API layer to land.

Usage:
    python -m scripts.agent_tools_demo --learner-id 4 --course-id 1 \
        --question "How do I structure a FastAPI project?"

    # exercise the assignment path
    python -m scripts.agent_tools_demo --learner-id 4 --course-id 1 \
        --assignment-id 2 --question "How should I approach this assignment?"

    # before Dev A's embeddings module lands
    AGENT_FAKE_EMBEDDINGS=1 python -m scripts.agent_tools_demo ...

Requires DATABASE_URL (see .env) and ANTHROPIC_API_KEY, or an `ant auth login`
profile.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlmodel import Session

from app.agent.tools import (
    AgentRetrievalError,
    AgentTools,
    EscalationReason,
    RetrievedChunk,
)
from app.core.database import engine

logger = logging.getLogger("agent_tools_demo")

MODEL = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """\
You are KodeBuddy, a learning assistant for KodeCamp students.

Ground every answer in content returned by your tools. If the tools return
nothing relevant, say so plainly and escalate to a trainer rather than
answering from general knowledge.

For questions about an assignment, guide the learner through the approach —
the concepts to apply and the order to tackle them in. Do not write the
solution for them.
"""


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks as the text handed back to the model."""
    if not chunks:
        return "No matching content found."

    return "\n\n".join(
        f"[chunk {chunk['chunk_id']} | course {chunk['course_id']}"
        f" | module {chunk['module_id']} | score {chunk['score']:.3f}]\n"
        f"{chunk['text']}"
        for chunk in chunks
    )


def _render_brief(brief) -> str:
    """
    Minimal rendering of a structured brief, for this harness only.

    The real path formats briefs in prompts/assignment_guidance.py (Dev C's
    file). This is deliberately a separate, simpler rendering rather than an
    import of that module's private helper — the harness should not break
    when Dev C renames something internal to her prompt design.
    """
    lines = [brief["title"], "", brief["description"]]
    if brief.get("due_date"):
        lines.append(f"\nDue: {brief['due_date']}")
    if brief.get("maximum_score") is not None:
        lines.append(f"Maximum score: {brief['maximum_score']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exercise the agent retrieval tools against a real DB."
    )
    parser.add_argument(
        "--learner-id",
        type=int,
        required=True,
        help="Authenticated learner's user id. All retrieval is scoped to it.",
    )
    parser.add_argument(
        "--course-id",
        type=int,
        required=True,
        help="Course the question is asked against.",
    )
    parser.add_argument(
        "--question",
        required=True,
        help="The learner's question.",
    )
    parser.add_argument(
        "--assignment-id",
        type=int,
        default=None,
        help="Optional assignment id, for the assignment-guidance path.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log every tool call and its result count.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,  # keep stdout clean for the final answer
    )

    try:
        import anthropic
        from anthropic import beta_tool
    except ImportError:
        print(
            "The 'anthropic' package is not installed. Run: pip install anthropic",
            file=sys.stderr,
        )
        return 2

    with Session(engine) as session:
        tools = AgentTools.for_learner(session, args.learner_id)

        if not tools.repository.is_enrolled(args.course_id):
            enrolled = tools.repository.enrolled_course_ids()
            print(
                f"Learner {args.learner_id} is not enrolled in course "
                f"{args.course_id}. Enrolled courses: {enrolled or 'none'}.\n"
                "Retrieval would correctly return nothing, so there is "
                "nothing to demonstrate.",
                file=sys.stderr,
            )
            return 1

        # --- Tool wrappers -------------------------------------------------
        # @beta_tool derives the JSON schema from these signatures and
        # docstrings, so they are written for the model to read. Each one
        # delegates to the learner-bound tool built above.

        @beta_tool
        def search_curriculum(query: str, module_id: int | None = None) -> str:
            """Search KodeCamp curriculum content for this course.

            Args:
                query: What to look for, in natural language.
                module_id: Optional module to narrow the search to.
            """
            chunks = tools.search_curriculum(
                query=query, course_id=args.course_id, module_id=module_id
            )
            logger.debug("search_curriculum -> %d chunks", len(chunks))
            return _format_chunks(chunks)

        @beta_tool
        def search_faqs(query: str) -> str:
            """Search frequently asked questions for this course.

            Args:
                query: What to look for, in natural language.
            """
            chunks = tools.search_faqs(query=query, course_id=args.course_id)
            logger.debug("search_faqs -> %d chunks", len(chunks))
            return _format_chunks(chunks)

        @beta_tool
        def get_assignment_brief(assignment_id: int) -> str:
            """Look up the brief for a specific assignment.

            Args:
                assignment_id: The assignment's id.
            """
            brief = tools.get_assignment_brief(assignment_id)
            logger.debug("get_assignment_brief(%s) -> %s", assignment_id, bool(brief))
            if brief is None:
                return "No brief available for that assignment."
            return _render_brief(brief)

        @beta_tool
        def escalate_to_trainer(detail: str) -> str:
            """Hand this question to a human trainer.

            Use when the curriculum content does not answer the question, or
            the question needs human judgement.

            Args:
                detail: Short explanation of why this needs a trainer.
            """
            # In the real path Dev C's confidence gate picks the category; this
            # harness has no gate, so it uses the closest fixed one and passes
            # the model's explanation through as free-form detail.
            escalation_id = tools.escalate_to_trainer(
                learner_id=args.learner_id,
                course_id=args.course_id,
                trainer_id=None,
                question=args.question,
                reason=EscalationReason.NO_RELEVANT_CONTEXT,
                detail=detail,
            )
            return (
                f"Escalated to a trainer (escalation #{escalation_id}). "
                "Tell the learner a trainer will follow up."
            )

        user_message = args.question
        if args.assignment_id is not None:
            user_message = (
                f"(About assignment {args.assignment_id}.) {args.question}"
            )

        client = anthropic.Anthropic()

        try:
            runner = client.beta.messages.tool_runner(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=[
                    search_curriculum,
                    search_faqs,
                    get_assignment_brief,
                    escalate_to_trainer,
                ],
                messages=[{"role": "user", "content": user_message}],
            )

            final_message = None
            for message in runner:
                final_message = message

        except AgentRetrievalError as exc:
            # Raised from inside a tool: the search never actually ran, which
            # must not be reported to the learner as "nothing was found".
            print(f"Retrieval unavailable: {exc}", file=sys.stderr)
            return 3
        except anthropic.NotFoundError:
            print(f"Unknown model or endpoint: {MODEL}", file=sys.stderr)
            return 4
        except anthropic.AuthenticationError:
            print(
                "Authentication failed. Set ANTHROPIC_API_KEY or run "
                "`ant auth login`.",
                file=sys.stderr,
            )
            return 4
        except anthropic.RateLimitError as exc:
            retry_after = exc.response.headers.get("retry-after", "60")
            print(f"Rate limited. Retry after {retry_after}s.", file=sys.stderr)
            return 5
        except anthropic.APIStatusError as exc:
            print(f"API error {exc.status_code}: {exc.message}", file=sys.stderr)
            return 5
        except anthropic.APIConnectionError:
            print("Network error reaching the Claude API.", file=sys.stderr)
            return 5

        if final_message is None:
            print("The model returned no messages.", file=sys.stderr)
            return 6

        if final_message.stop_reason == "refusal":
            details = getattr(final_message, "stop_details", None)
            print(
                "The model declined to answer"
                + (f" ({details.category})" if details else "")
                + ".",
                file=sys.stderr,
            )
            return 7

        # --- The final grounded answer, on stdout --------------------------
        answer = "\n".join(
            block.text for block in final_message.content if block.type == "text"
        ).strip()

        if not answer:
            print("The model returned no text content.", file=sys.stderr)
            return 6

        print(answer)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
