"""Azure OpenAI service - GPT-4o for grounded answer generation."""

import os
from app.config import env, env_bool


SYSTEM_PROMPT = """You are the JAYCO Dealer Technical Support Assistant. You help JAYCO trailer dealers 
answer technical questions about axles, suspension, hubs, bearings, brakes, and maintenance procedures.

IMPORTANT GUIDELINES:
- Only answer questions based on the provided document context.
- Always cite the specific document and page number when providing information.
- If the context doesn't contain enough information to fully answer the question, say so clearly.
- Use clear, professional language appropriate for trained service technicians.
- When describing procedures, use numbered steps.
- Highlight any safety warnings prominently.
- If a question is outside the scope of the provided documents, politely redirect to appropriate resources.

Format your response with:
1. A direct answer to the question
2. Relevant details and procedures
3. Safety warnings if applicable
4. References to source documents
"""


class OpenAIService:
    """Azure OpenAI GPT-4o service for answer generation."""

    def __init__(self):
        self.simulated_mode = env_bool("SIMULATED_MODE", True)
        self.openai_endpoint = env("AZURE_OPENAI_ENDPOINT")
        self.openai_api_key = env("AZURE_OPENAI_API_KEY")
        self.openai_api_version = env("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        self.openai_deployment = env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self._client = None

    def _get_client(self):
        """Get OpenAI client (lazy initialization)."""
        if self._client:
            return self._client

        if self.simulated_mode:
            return None

        from openai import AzureOpenAI

        self._client = AzureOpenAI(
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_api_key,
            api_version=self.openai_api_version,
        )
        return self._client

    async def generate_answer(
        self,
        question: str,
        context_chunks: list[dict],
        history: list[dict] | None = None,
    ) -> dict:
        """Generate a grounded answer using retrieved context."""
        if self.simulated_mode:
            return self._simulated_generate(question, context_chunks)

        return await self._live_generate(question, context_chunks, history)

    def _simulated_generate(self, question: str, context_chunks: list[dict]) -> dict:
        """Generate a simulated response for demo mode."""
        if not context_chunks:
            return {
                "answer": "I don't have enough information in the available documentation to answer that question. Please consult the JAYCO technical support team for assistance.",
                "confidence": 0.1,
            }

        # Build a contextual answer from the chunks
        context_text = "\n\n".join(
            [f"[{c['document_name']}, Page {c.get('page_number', 'N/A')}]: {c['chunk_text']}" for c in context_chunks]
        )

        # For demo, return the most relevant chunk as the answer with formatting
        primary_chunk = context_chunks[0]
        answer_parts = [
            f"Based on the JAYCO technical documentation, here is the information relevant to your question:\n",
            f"{primary_chunk['chunk_text']}",
        ]

        if len(context_chunks) > 1:
            answer_parts.append(f"\n\n**Additional relevant information:**")
            for chunk in context_chunks[1:3]:
                answer_parts.append(
                    f"\n- From *{chunk['document_name']}* (Page {chunk.get('page_number', 'N/A')}): "
                    f"{chunk['chunk_text'][:200]}..."
                )

        answer_parts.append(
            f"\n\n*Sources: {', '.join(set(c['document_name'] for c in context_chunks))}*"
        )

        return {
            "answer": "\n".join(answer_parts),
            "confidence": min(context_chunks[0].get("relevance_score", 0.5) + 0.3, 1.0),
        }

    async def _live_generate(
        self,
        question: str,
        context_chunks: list[dict],
        history: list[dict] | None = None,
    ) -> dict:
        """Generate answer using Azure OpenAI GPT-4o."""
        client = self._get_client()

        # Build context from retrieved chunks
        context_text = "\n\n---\n\n".join(
            [
                f"Document: {c['document_name']} | Page: {c.get('page_number', 'N/A')} | Source: {c.get('source_system', 'Unknown')}\n{c['chunk_text']}"
                for c in context_chunks
            ]
        )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history
        if history:
            for msg in history[-6:]:  # Keep last 6 messages for context
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        # Add current question with context
        user_message = f"""Based on the following documentation context, please answer the dealer's question.

CONTEXT:
{context_text}

QUESTION: {question}

Please provide a comprehensive answer citing the specific documents and page numbers."""

        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=self.openai_deployment,
            messages=messages,
            temperature=0.1,
            max_tokens=1500,
        )

        return {
            "answer": response.choices[0].message.content,
            "confidence": 0.85,
        }
