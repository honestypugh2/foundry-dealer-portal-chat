"""Azure AI Search service - Hybrid retrieval (keyword + semantic/vector)."""

import json
import os
from pathlib import Path
from app.config import env, env_bool
from app.models import SearchResult


# Simulated document chunks for demo mode
SIMULATED_CHUNKS = [
    {
        "document_name": "Axles and Suspension - Lippert Master Manual.pdf",
        "chunk_text": "Excessive tire wear can be caused by several factors: improper axle alignment, incorrect tire pressure, overloading beyond the axle's rated capacity, worn or damaged suspension components, or bent spindles. To diagnose, check tire wear patterns: inside edge wear indicates excessive negative camber, outside edge wear indicates positive camber or overloading, and center wear indicates over-inflation. Feathering or cupping suggests worn shock absorbers or loose components.",
        "page_number": 12,
        "source_system": "SharePoint",
        "tags": ["tire wear", "axle alignment", "suspension", "diagnosis"],
    },
    {
        "document_name": "Axles and Suspension - Lippert Master Manual.pdf",
        "chunk_text": "Regular suspension maintenance schedule: Every 3,000 miles or annually - inspect all suspension components for wear, damage, or looseness. Check equalizer bolts torque. Inspect leaf springs for cracks or separation. Verify shackle bolt condition. Lubricate wet bolts if equipped. Check shock absorber mounting bolts. Inspect hangers for cracks or bending. Verify axle alignment by measuring wheel-to-wheel dimensions.",
        "page_number": 45,
        "source_system": "SharePoint",
        "tags": ["maintenance", "suspension", "schedule", "inspection"],
    },
    {
        "document_name": "Hub, Drums, & Bearings Installation Instructions.pdf",
        "chunk_text": "Bearing Repack Procedure (Step-by-Step): 1) Remove dust cap using dust cap pliers. 2) Remove cotter pin and castle nut. 3) Remove outer bearing and hub/drum assembly. 4) Remove inner grease seal and inner bearing. 5) Clean all components with solvent and inspect for damage. 6) Pack bearings with high-temperature wheel bearing grease, ensuring grease fills all roller gaps. 7) Reinstall inner bearing and new grease seal. 8) Place hub on spindle and install outer bearing. 9) Install castle nut and torque to 50 ft-lbs while rotating hub, then back off to finger tight plus 1/6 turn. 10) Install new cotter pin and dust cap.",
        "page_number": 3,
        "source_system": "Revver",
        "tags": ["bearings", "repack", "procedure", "hub", "maintenance"],
    },
    {
        "document_name": "Hub, Drums, & Bearings Installation Instructions.pdf",
        "chunk_text": "High hub temperature and unusual noise diagnosis: Excessive hub temperature (over 150°F measured by infrared thermometer) combined with noise typically indicates: bearing failure, insufficient grease, contaminated grease (water intrusion), over-tightened castle nut, or damaged bearing race. IMMEDIATE ACTION REQUIRED: Stop travel immediately if hub is too hot to touch. Allow to cool completely before inspection. Remove hub and inspect bearings for bluing (heat damage), pitting, spalling, or cage damage. Replace bearings and races as a set if any damage is found.",
        "page_number": 7,
        "source_system": "Revver",
        "tags": ["hub temperature", "noise", "bearing failure", "diagnosis"],
    },
    {
        "document_name": "Jayco Axle Torque Procedures.pdf",
        "chunk_text": "Axle torque specifications for JAYCO trailers: U-bolt nuts: 7K axle = 110 ft-lbs, 8K axle = 150 ft-lbs. Spring eye bolts: 85 ft-lbs. Equalizer bolts: 120 ft-lbs. Hub castle nut: Torque to 50 ft-lbs while rotating, back off, then finger tight plus 1/6 turn. Always use new cotter pins. Re-torque after first 100 miles and then every 3,000 miles.",
        "page_number": 1,
        "source_system": "SharePoint",
        "tags": ["torque", "specifications", "u-bolt", "procedures"],
    },
    {
        "document_name": "Equalizer Chart Drawing.pdf",
        "chunk_text": "Beam Assembly Identification: 7K Beam Assembly - identified by part number stamped on the beam: 7K beams use 3-inch wide leaf springs with 5 leaves. The beam measures 2.5 inches in height. 8K Beam Assembly - identified by wider profile: 8K beams use 3-inch wide leaf springs with 6 leaves. The beam measures 3.0 inches in height. Visual identification: Count the number of leaves in the spring pack and measure beam height to determine rating.",
        "page_number": 1,
        "source_system": "SharePoint",
        "tags": ["beam assembly", "7K", "8K", "identification"],
    },
    {
        "document_name": "IS-System-Troubleshooting-Guide_v6-1.pdf",
        "chunk_text": "IS System Troubleshooting: If the trailer exhibits abnormal handling, sway, or uneven tire wear, verify: 1) All IS system components properly torqued. 2) No bent or damaged IS shackles. 3) Equalizer properly seated. 4) Spring hangers properly aligned. 5) No missing or loose hardware. Common failure modes include cracked equalizers (replace immediately), worn wet bolt bushings, and elongated spring eye holes.",
        "page_number": 15,
        "source_system": "Revver",
        "tags": ["troubleshooting", "IS system", "handling", "sway"],
    },
    {
        "document_name": "Deflection Measurement Procedure.pdf",
        "chunk_text": "Deflection Measurement: To measure suspension deflection and verify proper spring rate: 1) Park trailer on level surface. 2) Measure distance from frame bottom to ground (loaded). 3) Lift trailer until tires clear ground by 2 inches. 4) Measure distance from frame bottom to ground (unloaded). 5) Calculate deflection = unloaded measurement - loaded measurement. Acceptable deflection range: 2-4 inches for standard travel trailers. Excessive deflection indicates overloading or weakened springs.",
        "page_number": 1,
        "source_system": "SharePoint",
        "tags": ["deflection", "measurement", "spring rate", "procedure"],
    },
    {
        "document_name": "Jake Plate and Shock Bushing Guide.pdf",
        "chunk_text": "Jake Plate Installation: The Jake plate provides additional reinforcement at the spring-to-axle connection. Installation requires: 1) Lift trailer and support frame securely. 2) Remove existing U-bolts. 3) Position Jake plate between spring and axle with alignment tabs facing the spring. 4) Reinstall U-bolts through Jake plate holes. 5) Torque to specification (7K: 110 ft-lbs, 8K: 150 ft-lbs). Shock Bushing Replacement: Replace bushings when cracked, torn, or showing excessive wear. Use OEM-spec polyurethane bushings for improved durability.",
        "page_number": 2,
        "source_system": "Revver",
        "tags": ["jake plate", "shock bushing", "installation", "replacement"],
    },
    {
        "document_name": "Customer Advisory (Fixed Flange Nut Substitution) - 06-02-23.pdf",
        "chunk_text": "CUSTOMER ADVISORY: Fixed Flange Nut Substitution (June 2, 2023). Certain JAYCO units may have been shipped with standard hex nuts instead of flanged lock nuts on suspension U-bolts. Affected units should have U-bolt nuts replaced with Grade 8 flanged lock nuts (P/N: JC-FLN-875). Torque to 110 ft-lbs (7K) or 150 ft-lbs (8K). This substitution is required to maintain proper clamping force and prevent loosening due to vibration.",
        "page_number": 1,
        "source_system": "SharePoint",
        "tags": ["advisory", "flange nut", "u-bolt", "safety"],
    },
    {
        "document_name": "GM SERVICE BULLETIN FOR BRAKE DISCONNECT.pdf",
        "chunk_text": "GM Service Bulletin - Brake Disconnect: When servicing trailer brakes, always disconnect the breakaway cable before performing maintenance. Procedure: 1) Disconnect battery ground cable. 2) Remove breakaway switch pin. 3) Disconnect brake controller harness at tow vehicle connector. 4) Verify no voltage at brake magnets using multimeter. WARNING: Failure to disconnect brake system can result in unexpected brake actuation causing injury.",
        "page_number": 1,
        "source_system": "Revver",
        "tags": ["brake", "disconnect", "safety", "service bulletin"],
    },
]


class AISearchService:
    """Azure AI Search service with simulated fallback for demo mode."""

    def __init__(self):
        self.simulated_mode = env_bool("SIMULATED_MODE", True)
        self.search_endpoint = env("AZURE_SEARCH_ENDPOINT")
        self.search_index_name = env("AZURE_SEARCH_INDEX_NAME", "dealer-portal-docs")
        self.search_api_key = env("AZURE_SEARCH_API_KEY")
        self._client = None

    async def _get_client(self):
        """Get Azure AI Search client (live mode only)."""
        if self.simulated_mode:
            return None

        from azure.search.documents.aio import SearchClient
        from azure.core.credentials import AzureKeyCredential

        if not self._client:
            self._client = SearchClient(
                endpoint=self.search_endpoint,
                index_name=self.search_index_name,
                credential=AzureKeyCredential(self.search_api_key),
            )
        return self._client

    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_filter: str | None = None,
    ) -> list[SearchResult]:
        """Search for relevant document chunks."""
        if self.simulated_mode:
            return self._simulated_search(query, top_k, source_filter)

        return await self._live_search(query, top_k, source_filter)

    def _simulated_search(
        self,
        query: str,
        top_k: int,
        source_filter: str | None,
    ) -> list[SearchResult]:
        """Keyword-based simulated search for demo mode."""
        query_lower = query.lower()
        scored_results = []

        for chunk in SIMULATED_CHUNKS:
            # Filter by source if specified
            if source_filter and source_filter != "all":
                if chunk["source_system"].lower() != source_filter.lower():
                    continue

            # Simple relevance scoring based on keyword matching
            score = 0.0
            chunk_text_lower = chunk["chunk_text"].lower()
            tags = [t.lower() for t in chunk.get("tags", [])]

            # Score based on query terms present in chunk
            query_terms = query_lower.split()
            for term in query_terms:
                if term in chunk_text_lower:
                    score += 0.2
                if any(term in tag for tag in tags):
                    score += 0.3

            # Boost for exact phrase matches
            if query_lower in chunk_text_lower:
                score += 0.5

            if score > 0:
                scored_results.append(
                    SearchResult(
                        document_name=chunk["document_name"],
                        chunk_text=chunk["chunk_text"],
                        page_number=chunk["page_number"],
                        relevance_score=min(score, 1.0),
                        source_system=chunk["source_system"],
                        metadata={"tags": chunk.get("tags", [])},
                    )
                )

        # Sort by relevance and return top_k
        scored_results.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored_results[:top_k]

    async def _live_search(
        self,
        query: str,
        top_k: int,
        source_filter: str | None,
    ) -> list[SearchResult]:
        """Live Azure AI Search with hybrid retrieval."""
        from azure.search.documents.models import VectorizableTextQuery

        client = await self._get_client()

        vector_query = VectorizableTextQuery(
            text=query,
            k_nearest_neighbors=top_k,
            fields="content_vector",
        )

        filter_expr = None
        if source_filter and source_filter != "all":
            filter_expr = f"source_system eq '{source_filter}'"

        results = await client.search(
            search_text=query,
            vector_queries=[vector_query],
            filter=filter_expr,
            top=top_k,
            query_type="semantic",
            semantic_configuration_name="dealer-semantic-config",
        )

        search_results = []
        async for result in results:
            reranker = result.get("@search.reranker_score")
            search_results.append(
                SearchResult(
                    document_name=result.get("document_name", ""),
                    chunk_text=result.get("content", ""),
                    page_number=result.get("page_number"),
                    relevance_score=result.get("@search.score", 0.0),
                    reranker_score=reranker,
                    source_system=result.get("source_system", "AI Search"),
                    metadata={
                        "blob_url": result.get("blob_url", ""),
                        "metadata_storage_name": result.get("metadata_storage_name", ""),
                    },
                )
            )

        return search_results
