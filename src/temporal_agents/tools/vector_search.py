"""Execute vector similarity search against a Chroma collection."""
from __future__ import annotations

from temporal_agents.config.schemas import VectorCollectionConfig


async def execute_vector_search(config: VectorCollectionConfig, query: str) -> str:
    """Run similarity search and return formatted results."""
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model=config.embedding_model)
    vectorstore = Chroma(
        collection_name=config.collection_name,
        persist_directory=config.persist_directory,
        embedding_function=embeddings,
    )
    docs = await vectorstore.asimilarity_search(query, k=5)
    if not docs:
        return "No relevant documents found."
    return "\n\n---\n\n".join(
        f"**{doc.metadata.get('source', 'unknown')}**\n{doc.page_content}"
        for doc in docs
    )
