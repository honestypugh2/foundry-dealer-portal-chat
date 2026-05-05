"""Azure AI Search Integrated Vectorization Client

Manages Azure AI Search indexer + skillset pipeline with integrated vectorization.
Supports DocumentIntelligenceLayoutSkill, SplitSkill, and AzureOpenAIEmbeddingSkill.

This is the alternative extraction path (vs. Document Intelligence + manual chunking).
Set EXTRACTION_TYPE=integrated_vectorization in .env to use this pipeline.

Reference: https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import AzureCliCredential, ChainedTokenCredential, DefaultAzureCredential, ManagedIdentityCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.models import QueryType, VectorizedQuery
    SEARCH_SDK_AVAILABLE = True
except ImportError:
    SEARCH_SDK_AVAILABLE = False
    logger.warning("azure-search-documents not installed")

try:
    from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
    from azure.search.documents.indexes.models import (
        AzureOpenAIVectorizer,
        AzureOpenAIVectorizerParameters,
        HnswAlgorithmConfiguration,
        HnswParameters,
        RescoringOptions,
        ScalarQuantizationCompression,
        ScalarQuantizationParameters,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SearchableField,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )
    INDEX_SDK_AVAILABLE = True
except ImportError:
    INDEX_SDK_AVAILABLE = False
    logger.warning("azure-search-documents indexes models not available")

try:
    from openai import AzureOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.info("openai not installed, vector search unavailable")

# Agentic retrieval SDK classes (azure-search-documents>=12.0.0)
try:
    from azure.search.documents.indexes.models import (
        AzureOpenAIVectorizerParameters,
        KnowledgeBase,
        KnowledgeBaseAzureOpenAIModel,
        KnowledgeSourceReference,
        SearchIndexFieldReference,
        SearchIndexKnowledgeSource,
        SearchIndexKnowledgeSourceParameters,
    )
    AGENTIC_RETRIEVAL_AVAILABLE = True
except ImportError:
    AGENTIC_RETRIEVAL_AVAILABLE = False
    logger.info("Agentic retrieval SDK classes not available (need azure-search-documents>=12.0.0)")


# Load search config
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "search_config.json"
if _CONFIG_PATH.exists():
    with open(_CONFIG_PATH) as f:
        _FULL_CONFIG = json.load(f)
        _SEARCH_CONFIG = _FULL_CONFIG["search_config"]
        _VECTOR_SEARCH_CONFIG = _FULL_CONFIG.get("vector_search", {})
        _SEMANTIC_SEARCH_CONFIG = _FULL_CONFIG.get("semantic_search", {})
        _IV_CONFIG = _FULL_CONFIG.get("integrated_vectorization", {})
        _AGENTIC_CONFIG = _FULL_CONFIG.get("agentic_retrieval", {})
        _FOUNDRY_AGENT_CONFIG = _FULL_CONFIG.get("foundry_agent", {})
else:
    _FULL_CONFIG = {}
    _SEARCH_CONFIG = {}
    _VECTOR_SEARCH_CONFIG = {}
    _SEMANTIC_SEARCH_CONFIG = {}
    _IV_CONFIG = {}
    _AGENTIC_CONFIG = {}
    _FOUNDRY_AGENT_CONFIG = {}


class AzureAISearchClient:
    """
    Azure AI Search client for hybrid search against the dealer knowledge index.

    Architecture flow:
        Azure Blob Storage → Azure AI Search (indexer + skillset)
            → Azure AI Search Index (content + vector + semantic)
    """

    EMBEDDING_MODEL = _VECTOR_SEARCH_CONFIG.get("vectorizer", {}).get(
        "parameters", {}
    ).get("model_name", "text-embedding-3-large")
    EMBEDDING_DIMENSIONS = _VECTOR_SEARCH_CONFIG.get("dimensions", 3072)

    def __init__(self):
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.search_key = os.getenv("AZURE_SEARCH_API_KEY", "")
        self.index_name = os.getenv(
            "AZURE_SEARCH_INDEX_NAME",
            _SEARCH_CONFIG.get("index_name", "dealer-portal-docs"),
        )
        self.openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.openai_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

        # Lazy-init clients
        self._search_client: Optional[SearchClient] = None
        self._openai_client = None

        # Index field names from config
        self._vector_field = _SEARCH_CONFIG.get("vector_field", "content_vector")
        self._content_field = _SEARCH_CONFIG.get("content_field", "content")
        self._source_field = _SEARCH_CONFIG.get("source_field", "content_with_source")
        self._blob_url_field = _SEARCH_CONFIG.get("blob_url_field", "blob_url")
        self._filename_field = _SEARCH_CONFIG.get("filename_field", "metadata_storage_name")
        self._filepath_field = _SEARCH_CONFIG.get("filepath_field", "metadata_storage_path")
        self._parent_title_field = _SEARCH_CONFIG.get("parent_title_field", "document_name")
        self._document_type_field = _SEARCH_CONFIG.get("document_type_field", "source_system")
        self._parent_key_field = _SEARCH_CONFIG.get("parent_key_field", "chunk_parent_id")
        self._semantic_config = _SEARCH_CONFIG.get(
            "semantic_configuration", "dealer-semantic-config"
        )
        self._top_k = _SEARCH_CONFIG.get("top_k", 5)

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------
    def _get_credential(self):
        """Get Azure credential (key or managed identity)."""
        if self.search_key and not self.search_key.startswith("your_"):
            return AzureKeyCredential(self.search_key)
        return ChainedTokenCredential(
            ManagedIdentityCredential(),
            AzureCliCredential(),
        )

    # ------------------------------------------------------------------
    # Client initialization
    # ------------------------------------------------------------------
    def _get_search_client(self) -> SearchClient:
        """Get or create SearchClient."""
        if self._search_client:
            return self._search_client

        if not self.search_endpoint:
            raise ValueError("AZURE_SEARCH_ENDPOINT not set")

        self._search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.index_name,
            credential=self._get_credential(),
        )
        return self._search_client

    def _get_openai_client(self):
        """Get or create AzureOpenAI client."""
        if self._openai_client:
            return self._openai_client

        if not OPENAI_AVAILABLE:
            return None

        if self.openai_endpoint:
            # AzureOpenAI expects just the host (e.g. https://x.openai.azure.com)
            # Strip /openai/v1 or /openai suffixes that some configs include
            endpoint = self.openai_endpoint.rstrip("/")
            for suffix in ("/openai/v1", "/openai"):
                if endpoint.endswith(suffix):
                    endpoint = endpoint[: -len(suffix)]
                    break
            if self.openai_key and not self.openai_key.startswith("your_"):
                self._openai_client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_version=self.openai_api_version,
                    api_key=self.openai_key,
                )
            else:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider
                token_provider = get_bearer_token_provider(
                    DefaultAzureCredential(),
                    "https://cognitiveservices.azure.com/.default",
                )
                self._openai_client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_version=self.openai_api_version,
                    azure_ad_token_provider=token_provider,
                )
        return self._openai_client

    # ------------------------------------------------------------------
    # Index creation
    # ------------------------------------------------------------------
    def create_index(self) -> bool:
        """Create the dealer portal search index with HNSW, scalar quantization, and semantic config."""
        if not INDEX_SDK_AVAILABLE:
            logger.error("azure-search-documents indexes models not available")
            return False

        if not self.search_endpoint:
            logger.error("AZURE_SEARCH_ENDPOINT not set")
            return False

        index_client = SearchIndexClient(
            endpoint=self.search_endpoint,
            credential=self._get_credential(),
        )

        # -- Vector search: HNSW + optional Scalar Quantization --
        algo_cfg = _VECTOR_SEARCH_CONFIG.get("algorithm", {})
        hnsw_params = algo_cfg.get("parameters", {})
        hnsw = HnswAlgorithmConfiguration(
            name=algo_cfg.get("name", "dealer-hnsw-config"),
            parameters=HnswParameters(
                metric=hnsw_params.get("metric", "cosine"),
                m=hnsw_params.get("m", 4),
                ef_construction=hnsw_params.get("ef_construction", 400),
                ef_search=hnsw_params.get("ef_search", 500),
            ),
        )

        use_compression = os.getenv("SEARCH_USE_COMPRESSION", "true").lower() == "true"
        compression_cfg = _VECTOR_SEARCH_CONFIG.get("compression", {})
        compression_params = compression_cfg.get("parameters", {})
        rescoring_cfg = compression_cfg.get("rescoring_options", {})

        scalar_quantization = None
        if use_compression:
            scalar_quantization = ScalarQuantizationCompression(
                compression_name=compression_cfg.get("name", "dealer-scalar-quantization"),
                parameters=ScalarQuantizationParameters(
                    quantized_data_type=compression_params.get("quantized_data_type", "int8"),
                ),
                rescoring_options=RescoringOptions(
                    enable_rescoring=rescoring_cfg.get("enable_rescoring", True),
                    default_oversampling=rescoring_cfg.get("default_oversampling", 4),
                ),
            )

        # -- Query-time vectorizer --
        aoai_endpoint = self.openai_endpoint
        if "/openai" in aoai_endpoint:
            aoai_endpoint = aoai_endpoint.split("/openai")[0]

        vectorizer_cfg = _VECTOR_SEARCH_CONFIG.get("vectorizer", {})
        vectorizer_params = vectorizer_cfg.get("parameters", {})
        vectorizer_name = vectorizer_cfg.get("name", "dealer-azure-openai-vectorizer")
        vectorizer = AzureOpenAIVectorizer(
            vectorizer_name=vectorizer_name,
            parameters=AzureOpenAIVectorizerParameters(
                resource_url=aoai_endpoint,
                deployment_name=vectorizer_params.get("deployment_name", self.EMBEDDING_MODEL),
                model_name=vectorizer_params.get("model_name", self.EMBEDDING_MODEL),
            ),
        )

        profile_cfg = _VECTOR_SEARCH_CONFIG.get("profile", {})
        vector_search = VectorSearch(
            algorithms=[hnsw],
            compressions=[scalar_quantization] if scalar_quantization else [],
            vectorizers=[vectorizer],
            profiles=[
                VectorSearchProfile(
                    name=profile_cfg.get("name", "dealer-vector-profile"),
                    algorithm_configuration_name=algo_cfg.get("name", "dealer-hnsw-config"),
                    compression_name=compression_cfg.get("name", "dealer-scalar-quantization") if scalar_quantization else None,
                    vectorizer_name=vectorizer_name,
                )
            ],
        )

        # -- Semantic search --
        sem_cfg_name = _SEMANTIC_SEARCH_CONFIG.get("configuration_name", self._semantic_config)
        sem_prioritized = _SEMANTIC_SEARCH_CONFIG.get("prioritized_fields", {})
        sem_content_fields = sem_prioritized.get("content_fields", [self._content_field])
        sem_title_field = sem_prioritized.get("title_field", None)
        sem_keywords_fields = sem_prioritized.get("keywords_fields", [])

        semantic_config = SemanticConfiguration(
            name=sem_cfg_name,
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name=sem_title_field) if sem_title_field else None,
                content_fields=[SemanticField(field_name=f) for f in sem_content_fields],
                keywords_fields=[SemanticField(field_name=f) for f in sem_keywords_fields] if sem_keywords_fields else None,
            ),
        )

        semantic_search = SemanticSearch(
            default_configuration_name=sem_cfg_name,
            configurations=[semantic_config],
        )

        # -- Index fields --
        fields = [
            SearchField(name="id", type=SearchFieldDataType.String, key=True, filterable=True, analyzer_name="keyword"),
            SimpleField(name=self._blob_url_field, type=SearchFieldDataType.String),
            SearchableField(name=self._content_field, type=SearchFieldDataType.String),
            SearchableField(name=self._source_field, type=SearchFieldDataType.String),
            SearchableField(name=self._filename_field, type=SearchFieldDataType.String, filterable=True),
            SearchableField(name=self._filepath_field, type=SearchFieldDataType.String, filterable=True),
            SearchableField(name=self._parent_title_field, type=SearchFieldDataType.String, filterable=True),
            SearchableField(name=self._document_type_field, type=SearchFieldDataType.String, filterable=True),
            SimpleField(
                name=self._parent_key_field,
                type=SearchFieldDataType.String,
                filterable=True,
            ),
            SimpleField(name="page_number", type=SearchFieldDataType.Int32, filterable=True),
            SimpleField(name="chunk_index", type=SearchFieldDataType.Int32),
            SearchField(
                name=self._vector_field,
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.EMBEDDING_DIMENSIONS,
                vector_search_profile_name=profile_cfg.get("name", "dealer-vector-profile"),
            ),
        ]

        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )

        try:
            index_client.create_or_update_index(index)
            logger.info(f"Index '{self.index_name}' created/updated")
            return True
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False

    # ------------------------------------------------------------------
    # Integrated Vectorization: Indexer + Skillset
    # ------------------------------------------------------------------
    def create_integrated_vectorization_pipeline(self) -> bool:
        """
        Create the full integrated vectorization pipeline:
        - Data source (blob storage)
        - Skillset (DocumentIntelligenceLayoutSkill + SplitSkill + EmbeddingSkill)
        - Indexer with index projections

        This replaces manual document extraction + chunking + embedding.
        """
        if not self.search_endpoint:
            logger.error("AZURE_SEARCH_ENDPOINT not set")
            return False

        try:
            from azure.search.documents.indexes import SearchIndexerClient
            from azure.search.documents.indexes.models import (
                SearchIndexer,
                SearchIndexerDataContainer,
                SearchIndexerDataSourceConnection,
                SearchIndexerSkillset,
                IndexProjectionMode,
                SearchIndexerIndexProjection,
                SearchIndexerIndexProjectionSelector,
                SearchIndexerIndexProjectionsParameters,
                InputFieldMappingEntry,
                OutputFieldMappingEntry,
            )
        except ImportError:
            logger.error("Required indexer models not available")
            return False

        indexer_client = SearchIndexerClient(
            endpoint=self.search_endpoint,
            credential=self._get_credential(),
        )

        container_name = os.getenv(
            "AZURE_STORAGE_CONTAINER_PORTAL",
            _FULL_CONFIG.get("blob_storage", {}).get("container_name", "portal-docs"),
        )
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")

        # Step 1: Data source connection
        data_source_name = _IV_CONFIG.get("data_source_name", "dealer-docs-blob-source")
        try:
            data_source = SearchIndexerDataSourceConnection(
                name=data_source_name,
                type="azureblob",
                connection_string=connection_string,
                container=SearchIndexerDataContainer(name=container_name),
            )
            indexer_client.create_or_update_data_source_connection(data_source)
            logger.info(f"Data source '{data_source_name}' created/updated")
        except Exception as e:
            logger.error(f"Failed to create data source: {e}")
            return False

        # Step 2: Skillset with index projections
        skillset_name = _IV_CONFIG.get("skillset_name", "dealer-docs-skillset")
        chunking_cfg = _IV_CONFIG.get("chunking", {})
        projections_cfg = _IV_CONFIG.get("index_projections", {})

        aoai_endpoint = self.openai_endpoint
        if "/openai" in aoai_endpoint:
            aoai_endpoint = aoai_endpoint.split("/openai")[0]

        # Build skills list from config
        skills_json = []
        for skill_cfg in _IV_CONFIG.get("skills", []):
            skill_type = skill_cfg.get("type", "")
            if skill_type == "DocumentIntelligenceLayoutSkill":
                skills_json.append({
                    "@odata.type": "#Microsoft.Skills.Util.DocumentIntelligenceLayoutSkill",
                    "name": skill_cfg.get("name", "DocumentLayoutSkill"),
                    "context": skill_cfg.get("context", "/document"),
                    "outputMode": skill_cfg.get("output_mode", "oneToMany"),
                    "markdownHeaderDepth": skill_cfg.get("markdown_headers_depth", "h3"),
                    "inputs": [{"name": "file_data", "source": "/document/file_data"}],
                    "outputs": [{"name": "markdown_document", "targetName": "markdownDocument"}],
                })
            elif skill_type == "SplitSkill":
                skills_json.append({
                    "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
                    "name": skill_cfg.get("name", "TextSplitSkill"),
                    "context": "/document",
                    "textSplitMode": skill_cfg.get("text_split_mode", "pages"),
                    "maximumPageLength": chunking_cfg.get("maximum_length", 2000),
                    "pageOverlapLength": chunking_cfg.get("overlap_length", 200),
                    "inputs": [{"name": "text", "source": "/document/markdownDocument"}],
                    "outputs": [{"name": "textItems", "targetName": "pages"}],
                })
            elif skill_type == "AzureOpenAIEmbeddingSkill":
                skills_json.append({
                    "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
                    "name": skill_cfg.get("name", "AzureOpenAIEmbeddingSkill"),
                    "context": "/document/pages/*",
                    "resourceUri": aoai_endpoint,
                    "deploymentId": skill_cfg.get("deployment_id", self.EMBEDDING_MODEL),
                    "modelName": skill_cfg.get("model_name", self.EMBEDDING_MODEL),
                    "dimensions": skill_cfg.get("dimensions", self.EMBEDDING_DIMENSIONS),
                    "inputs": [{"name": "text", "source": "/document/pages/*"}],
                    "outputs": [{"name": "embedding", "targetName": "content_vector"}],
                })

        # Index projections
        projection_mappings = []
        for mapping in projections_cfg.get("mappings", []):
            projection_mappings.append(
                InputFieldMappingEntry(name=mapping["name"], source=mapping["source"])
            )

        index_projections = SearchIndexerIndexProjection(
            selectors=[
                SearchIndexerIndexProjectionSelector(
                    target_index_name=projections_cfg.get("target_index_name", self.index_name),
                    parent_key_field_name=projections_cfg.get("parent_key_field_name", "chunk_parent_id"),
                    source_context=projections_cfg.get("source_context", "/document/pages/*"),
                    mappings=projection_mappings,
                )
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.GENERATED_KEY_AS_ID,
            ),
        )

        try:
            # Note: Skillset creation via REST may be needed for custom skills
            # Using SDK for standard skills
            skillset = SearchIndexerSkillset(
                name=skillset_name,
                description="JAYCO dealer docs: Layout extraction + chunking + embedding",
                skills=skills_json,
                index_projections=index_projections,
            )
            indexer_client.create_or_update_skillset(skillset)
            logger.info(f"Skillset '{skillset_name}' created/updated")
        except Exception as e:
            logger.error(f"Failed to create skillset: {e}")
            return False

        # Step 3: Indexer
        indexer_name = _IV_CONFIG.get("indexer_name", "dealer-docs-indexer")
        try:
            indexer = SearchIndexer(
                name=indexer_name,
                data_source_name=data_source_name,
                target_index_name=self.index_name,
                skillset_name=skillset_name,
                description="JAYCO dealer docs indexer with integrated vectorization",
            )
            indexer_client.create_or_update_indexer(indexer)
            logger.info(f"Indexer '{indexer_name}' created/updated")
        except Exception as e:
            logger.error(f"Failed to create indexer: {e}")
            return False

        return True

    def run_indexer(self) -> bool:
        """Trigger the indexer to run."""
        try:
            from azure.search.documents.indexes import SearchIndexerClient

            indexer_client = SearchIndexerClient(
                endpoint=self.search_endpoint,
                credential=self._get_credential(),
            )
            indexer_name = _IV_CONFIG.get("indexer_name", "dealer-docs-indexer")
            indexer_client.run_indexer(indexer_name)
            logger.info(f"Indexer '{indexer_name}' triggered")
            return True
        except Exception as e:
            logger.error(f"Failed to run indexer: {e}")
            return False

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------
    def generate_embedding(self, text: str, max_retries: int = 5) -> list[float] | None:
        """Generate embedding vector using the configured embedding model."""
        client = self._get_openai_client()
        if not client:
            return None

        for attempt in range(max_retries):
            try:
                response = client.embeddings.create(
                    input=text, model=self.EMBEDDING_MODEL
                )
                return response.data[0].embedding
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RateLimitError" in type(e).__name__:
                    wait = 2 ** attempt + 1
                    logger.warning(f"Rate limited (attempt {attempt + 1}/{max_retries}), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.warning(f"Embedding generation failed: {e}")
                    return None

        logger.warning("Embedding generation failed after max retries")
        return None

    # ------------------------------------------------------------------
    # Hybrid Search
    # ------------------------------------------------------------------
    def hybrid_search(
        self,
        user_query: str,
        embedding: list[float] | None = None,
        top: int | None = None,
        source_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute hybrid search: full-text + vector + semantic ranker.

        Args:
            user_query: The user's natural-language query.
            embedding: Pre-computed embedding vector. If None, one will be generated.
            top: Number of results to return (defaults to config top_k).
            source_filter: Optional filter by source_system value.

        Returns:
            List of hit dicts with keys: content, document_name, page_number,
            source_system, score, reranker_score, blob_url, chunk_parent_id.
        """
        top = top or self._top_k
        search_client = self._get_search_client()

        search_kwargs: dict[str, Any] = {
            "search_text": user_query,
            "top": top,
            "include_total_count": True,
            "query_type": QueryType.SEMANTIC,
            "semantic_configuration_name": self._semantic_config,
        }

        # Vector leg
        vec = embedding or self.generate_embedding(user_query)
        if vec:
            search_kwargs["vector_queries"] = [
                VectorizedQuery(
                    vector=vec,
                    k_nearest_neighbors=top,
                    fields=self._vector_field,
                )
            ]

        # Optional source filter
        if source_filter:
            search_kwargs["filter"] = f"{self._document_type_field} eq '{source_filter}'"

        try:
            results = search_client.search(**search_kwargs)
            hits: list[dict[str, Any]] = []

            for result in results:
                content = result.get(self._content_field, "")
                blob_url = result.get(self._blob_url_field, "")

                hits.append({
                    "content": content,
                    "document_name": result.get(self._parent_title_field, ""),
                    "page_number": result.get("page_number"),
                    "source_system": result.get(self._document_type_field, ""),
                    "chunk_parent_id": result.get(self._parent_key_field, ""),
                    "fileName": result.get(self._filename_field, ""),
                    "filePath": result.get(self._filepath_field, ""),
                    "score": result.get("@search.score", 0),
                    "reranker_score": result.get("@search.reranker_score"),
                    "blob_url": blob_url,
                })

            logger.info(f"Hybrid search returned {len(hits)} results")
            return hits
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Upload documents (manual path)
    # ------------------------------------------------------------------
    def upload_documents(self, documents: list[dict], max_retries: int = 5) -> int:
        """
        Upload pre-processed documents to the search index.

        Args:
            documents: List of document dicts matching the index schema.
            max_retries: Max retry attempts per batch on rate-limit errors.

        Returns:
            Number of successfully uploaded documents.
        """
        search_client = self._get_search_client()
        batch_size = 100
        total_succeeded = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            for attempt in range(max_retries):
                try:
                    result = search_client.upload_documents(documents=batch)
                    succeeded = sum(1 for r in result if r.succeeded)
                    total_succeeded += succeeded
                    logger.info(f"Uploaded batch {i // batch_size + 1}: {succeeded}/{len(batch)}")
                    break
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "Too Many Requests" in error_str:
                        wait = 2 ** attempt + 1
                        logger.warning(f"Rate limited uploading batch {i // batch_size + 1} (attempt {attempt + 1}/{max_retries}), retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        logger.error(f"Failed to upload batch: {e}")
                        break
            else:
                logger.error(f"Batch {i // batch_size + 1} failed after {max_retries} retries")

        return total_succeeded

    # ------------------------------------------------------------------
    # Agentic Retrieval: Knowledge Source + Knowledge Base + MCP
    # ------------------------------------------------------------------
    def get_mcp_endpoint(self) -> str:
        """Return the MCP endpoint URL for the knowledge base."""
        kb_name = _AGENTIC_CONFIG.get("knowledge_base_name", "dealer-knowledge-base")
        api_version = _AGENTIC_CONFIG.get("mcp", {}).get("api_version", "2025-11-01-Preview")
        return f"{self.search_endpoint}/knowledgebases/{kb_name}/mcp?api-version={api_version}"

    def create_knowledge_source(self) -> bool:
        """Create or update the knowledge source for agentic retrieval."""
        if not AGENTIC_RETRIEVAL_AVAILABLE:
            logger.error("Agentic retrieval SDK classes not available")
            return False

        if not self.search_endpoint:
            logger.error("AZURE_SEARCH_ENDPOINT not set")
            return False

        ks_name = _AGENTIC_CONFIG.get("knowledge_source_name", "dealer-knowledge-source")
        ks_description = _AGENTIC_CONFIG.get(
            "knowledge_source_description",
            "Knowledge source for JAYCO dealer technical documentation",
        )
        source_data_fields = _AGENTIC_CONFIG.get("source_data_fields", ["id", "content"])
        search_fields = _AGENTIC_CONFIG.get("search_fields", ["content", "document_name", "source_system"])
        semantic_config_name = _AGENTIC_CONFIG.get("semantic_configuration_name", "dealer-semantic-config")

        index_client = SearchIndexClient(
            endpoint=self.search_endpoint,
            credential=self._get_credential(),
        )

        ks = SearchIndexKnowledgeSource(
            name=ks_name,
            description=ks_description,
            search_index_parameters=SearchIndexKnowledgeSourceParameters(
                search_index_name=self.index_name,
                source_data_fields=[
                    SearchIndexFieldReference(name=field)
                    for field in source_data_fields
                ],
                search_fields=[
                    SearchIndexFieldReference(name=field)
                    for field in search_fields
                ],
                semantic_configuration_name=semantic_config_name,
            ),
        )

        try:
            index_client.create_or_update_knowledge_source(knowledge_source=ks)
            logger.info(f"Knowledge source '{ks_name}' created/updated")
            return True
        except Exception as e:
            logger.error(f"Failed to create knowledge source: {e}")
            return False

    def create_knowledge_base(self) -> bool:
        """Create or update the knowledge base for agentic retrieval."""
        if not AGENTIC_RETRIEVAL_AVAILABLE:
            logger.error("Agentic retrieval SDK classes not available")
            return False

        if not self.search_endpoint:
            logger.error("AZURE_SEARCH_ENDPOINT not set")
            return False

        ks_name = _AGENTIC_CONFIG.get("knowledge_source_name", "dealer-knowledge-source")
        kb_name = _AGENTIC_CONFIG.get("knowledge_base_name", "dealer-knowledge-base")
        output_mode_str = _AGENTIC_CONFIG.get("output_mode", "ANSWER_SYNTHESIS")
        reasoning_effort_str = _AGENTIC_CONFIG.get("retrieval_reasoning_effort", "medium")

        # Resolve the OpenAI endpoint for the chat completion model
        aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        if "/openai" in aoai_endpoint:
            aoai_endpoint = aoai_endpoint.split("/openai")[0]
        # KB model for query planning (prefer lightweight model for speed)
        gpt_deployment = os.getenv(
            "AZURE_OPENAI_KB_MODEL_DEPLOYMENT",
            _AGENTIC_CONFIG.get("kb_model_deployment", "gpt-4.1-mini"),
        )
        gpt_model = os.getenv(
            "AZURE_OPENAI_KB_MODEL_NAME",
            _AGENTIC_CONFIG.get("kb_model_name", gpt_deployment),
        )

        # Retrieval and answer instructions from foundry_agent config
        retrieval_instructions = _FOUNDRY_AGENT_CONFIG.get("retrieval_instructions", "")
        answer_instructions = _FOUNDRY_AGENT_CONFIG.get("answer_instructions", "")

        # Use preview API version for KB creation (stable 2026-04-01 doesn't support outputMode)
        mcp_config = _AGENTIC_CONFIG.get("mcp", {})
        kb_api_version = mcp_config.get("api_version", "2025-11-01-Preview")
        index_client = SearchIndexClient(
            endpoint=self.search_endpoint,
            credential=self._get_credential(),
            api_version=kb_api_version,
        )

        # Build model parameters using AzureOpenAIVectorizerParameters
        # (serializes to resourceUri/deploymentId/modelName which the API expects)
        aoai_params = AzureOpenAIVectorizerParameters(
            resource_url=aoai_endpoint,
            deployment_name=gpt_deployment,
            model_name=gpt_model,
        )

        # Build knowledge base with model, output mode, and reasoning effort
        knowledge_base = KnowledgeBase(
            name=kb_name,
            knowledge_sources=[
                KnowledgeSourceReference(name=ks_name),
            ],
            models=[KnowledgeBaseAzureOpenAIModel(
                azure_open_ai_parameters=aoai_params,
            )],
        )

        # Set output mode (dict-style — SDK v12 doesn't have typed enums for these)
        # Valid values: "extractiveData" or "answerSynthesis"
        output_mode_map = {
            "EXTRACTIVE_DATA": "extractiveData",
            "ANSWER_SYNTHESIS": "answerSynthesis",
            "extractiveData": "extractiveData",
            "answerSynthesis": "answerSynthesis",
        }
        knowledge_base["outputMode"] = output_mode_map.get(output_mode_str, "answerSynthesis")

        # Set reasoning effort as object with kind (API expects {"kind": "minimal"|"low"|"medium"})
        knowledge_base["retrievalReasoningEffort"] = {"kind": reasoning_effort_str}

        # Set retrieval/answer instructions if configured
        if retrieval_instructions:
            knowledge_base["retrievalInstructions"] = retrieval_instructions
        if answer_instructions:
            knowledge_base["answerInstructions"] = answer_instructions

        try:
            index_client.create_or_update_knowledge_base(knowledge_base=knowledge_base)
            logger.info(f"Knowledge base '{kb_name}' created/updated")
            logger.info(f"MCP endpoint: {self.get_mcp_endpoint()}")
            return True
        except Exception as e:
            logger.error(f"Failed to create knowledge base: {e}")
            return False

    def create_project_connection(self) -> bool:
        """Create or update the MCP project connection in Azure AI Foundry.

        This uses the ARM REST API to register the MCP endpoint as a
        RemoteTool connection in the Foundry project so agents can access it.
        """
        import requests
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        project_resource_id = os.getenv("AZURE_AI_PROJECT_RESOURCE_ID", "")
        if not project_resource_id:
            logger.warning(
                "AZURE_AI_PROJECT_RESOURCE_ID not set — cannot create project connection. "
                "Set it to: /subscriptions/<sub>/resourceGroups/<rg>"
                "/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>"
            )
            return False

        connection_name = _AGENTIC_CONFIG.get("mcp", {}).get(
            "project_connection_name", "dealer-knowledge-mcp-connection"
        )
        mcp_endpoint = self.get_mcp_endpoint()

        credential = DefaultAzureCredential()
        bearer_token_provider = get_bearer_token_provider(
            credential, "https://management.azure.com/.default"
        )

        headers = {
            "Authorization": f"Bearer {bearer_token_provider()}",
            "Content-Type": "application/json",
        }

        url = (
            f"https://management.azure.com{project_resource_id}"
            f"/connections/{connection_name}?api-version=2025-10-01-preview"
        )

        payload = {
            "name": connection_name,
            "type": "Microsoft.MachineLearningServices/workspaces/connections",
            "properties": {
                "authType": "CustomKeys",
                "category": "RemoteTool",
                "target": mcp_endpoint,
                "isSharedToAll": True,
                "credentials": {
                    "keys": {
                        "api-key": os.getenv("AZURE_SEARCH_API_KEY", ""),
                    },
                },
                "metadata": {"ApiType": "Azure"},
            },
        }

        try:
            response = requests.put(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"Project connection '{connection_name}' created/updated")
            return True
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create project connection: {e} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to create project connection: {e}")
            return False
