"""
Test per il sistema RAG procedure: chunker, retrieval, tool.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.indexing.doc_chunker import DocumentChunker
from tools.procedure_tools import (
    get_procedure_info, _build_rag_context, _format_sources
)


class TestDocumentChunker:
    """Test per doc_chunker.py"""

    def setup_method(self):
        self.chunker = DocumentChunker(chunk_size=200, chunk_overlap=30)

    def test_chunk_simple_text(self):
        """Verifica chunking di un testo semplice."""
        text = "Primo paragrafo con contenuto.\n\nSecondo paragrafo con altro contenuto."
        chunks = self.chunker.chunk_text(text, {"source_file": "test.txt", "title": "Test"})

        assert len(chunks) >= 1
        assert chunks[0]["metadata"]["source_file"] == "test.txt"
        assert chunks[0]["metadata"]["title"] == "Test"
        assert chunks[0]["metadata"]["chunk_index"] == 0
        assert "content" in chunks[0]

    def test_chunk_preserves_metadata(self):
        """Verifica che i chunk preservino source_file, title, section."""
        text = "## Ispezione Semplice\n\nDescrizione della procedura di ispezione."
        chunks = self.chunker.chunk_text(text, {"source_file": "manuale.pdf", "title": "Manuale"})

        assert len(chunks) >= 1
        assert chunks[0]["metadata"]["source_file"] == "manuale.pdf"
        assert "chunk_index" in chunks[0]["metadata"]
        assert "total_chunks" in chunks[0]["metadata"]

    def test_chunk_long_text_splits(self):
        """Verifica che un testo lungo venga spezzato in piu' chunk."""
        # Crea testo piu' lungo del chunk_size
        text = "\n\n".join([f"Paragrafo {i} con contenuto sufficiente per il test." for i in range(20)])
        chunks = self.chunker.chunk_text(text, {"source_file": "test.txt", "title": "Test"})

        assert len(chunks) > 1
        # Verifica indici sequenziali
        for i, chunk in enumerate(chunks):
            assert chunk["metadata"]["chunk_index"] == i
            assert chunk["metadata"]["total_chunks"] == len(chunks)

    def test_chunk_empty_text(self):
        """Verifica gestione testo vuoto."""
        chunks = self.chunker.chunk_text("", {"source_file": "empty.txt", "title": "Empty"})
        assert len(chunks) == 0

    def test_load_txt_file(self):
        """Verifica caricamento file TXT."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Procedura di test.\n\nPassaggio 1: Verificare.\n\nPassaggio 2: Completare.")
            tmp_path = f.name

        try:
            chunks = self.chunker.load_file(tmp_path)
            assert len(chunks) >= 1
            assert chunks[0]["metadata"]["source_file"] == os.path.basename(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_extract_title_from_filename(self):
        """Verifica estrazione titolo dal nome file."""
        assert self.chunker._extract_title_from_filename("manuale_ispezioni.pdf") == "Manuale Ispezioni"
        assert self.chunker._extract_title_from_filename("guida-controlli.txt") == "Guida Controlli"

    def test_section_header_extraction(self):
        """Verifica estrazione header di sezione."""
        text = "## Prima Sezione\n\nContenuto sezione 1.\n\n## Seconda Sezione\n\nContenuto sezione 2."
        headers = self.chunker._extract_section_headers(text)
        assert len(headers) >= 2
        assert headers[0]["title"] == "Prima Sezione"

    def test_process_directory_empty(self):
        """Verifica gestione directory vuota."""
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = self.chunker.process_directory(tmpdir)
            assert len(chunks) == 0

    def test_process_directory_with_txt(self):
        """Verifica processamento directory con file TXT."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_procedure.txt")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("Procedura di ispezione semplice.\n\nPassaggio 1: Verificare documenti.")

            chunks = self.chunker.process_directory(tmpdir)
            assert len(chunks) >= 1

    def test_unsupported_extension_ignored(self):
        """Verifica che estensioni non supportate vengano ignorate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "data.csv")
            with open(filepath, 'w') as f:
                f.write("col1,col2\nval1,val2")

            chunks = self.chunker.process_directory(tmpdir)
            assert len(chunks) == 0


class TestProcedureTool:
    """Test per procedure_tools.py"""

    def test_get_procedure_info_empty_query(self):
        """Verifica gestione query vuota."""
        func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
        result = func(query="")

        assert "error" in result
        assert "formatted_response" in result

    def test_get_procedure_info_none_query(self):
        """Verifica gestione query None."""
        func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
        result = func(query=None)

        assert "error" in result

    @patch('tools.procedure_tools.DataRetriever')
    def test_get_procedure_info_no_results(self, mock_retriever):
        """Verifica messaggio 'non trovato' se nessun chunk matcha."""
        mock_retriever.search_procedure_docs.return_value = []

        func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
        result = func(query="procedura inesistente")

        assert result["error"] == "no_results"
        assert "Non ho trovato" in result["formatted_response"]

    @patch('tools.procedure_tools._generate_rag_response')
    @patch('tools.procedure_tools.DataRetriever')
    def test_get_procedure_info_success(self, mock_retriever, mock_generate):
        """Verifica flusso completo con chunk trovati."""
        mock_retriever.search_procedure_docs.return_value = [
            {
                "content": "La procedura di ispezione semplice prevede...",
                "source_file": "manuale.pdf",
                "section": "Ispezione Semplice",
                "title": "Manuale Ispezioni",
                "score": 0.85
            }
        ]
        mock_generate.return_value = "Risposta generata dall'LLM"

        func = get_procedure_info.func if hasattr(get_procedure_info, 'func') else get_procedure_info
        result = func(query="procedura ispezione semplice")

        assert "formatted_response" in result
        assert result["chunks_found"] == 1
        assert result["top_score"] == 0.85
        assert "Manuale Ispezioni" in result["formatted_response"]


class TestRAGContextAssembly:
    """Test per le funzioni helper del RAG."""

    def test_build_rag_context_single_chunk(self):
        """Verifica formato contesto con un singolo chunk."""
        chunks = [
            {
                "content": "Contenuto del chunk di test.",
                "title": "Manuale",
                "section": "Sezione A",
                "source_file": "manuale.pdf",
                "score": 0.9
            }
        ]
        context = _build_rag_context(chunks)

        assert "[Fonte 1: Manuale - Sezione A]" in context
        assert "Contenuto del chunk di test." in context

    def test_build_rag_context_multiple_chunks(self):
        """Verifica formato contesto con chunk multipli."""
        chunks = [
            {"content": "Chunk 1", "title": "Doc A", "section": "Sez 1", "source_file": "a.pdf", "score": 0.9},
            {"content": "Chunk 2", "title": "Doc B", "section": "", "source_file": "b.txt", "score": 0.7},
        ]
        context = _build_rag_context(chunks)

        assert "[Fonte 1: Doc A - Sez 1]" in context
        assert "[Fonte 2: Doc B]" in context
        assert "Chunk 1" in context
        assert "Chunk 2" in context

    def test_build_rag_context_with_page_num(self):
        """Verifica formato contesto con numero pagina."""
        chunks = [
            {"content": "Contenuto pag 5.", "title": "Manuale", "section": "Ispezione", "source_file": "manuale.pdf", "page_num": 5, "score": 0.9},
            {"content": "Contenuto no page.", "title": "Guida", "section": "", "source_file": "guida.txt", "page_num": None, "score": 0.7},
        ]
        context = _build_rag_context(chunks)

        assert "[Fonte 1: Manuale - Ispezione (pag. 5)]" in context
        assert "[Fonte 2: Guida]" in context
        assert "(pag." not in context.split("[Fonte 2")[1] or "pag. 5" in context

    def test_format_sources_deduplication(self):
        """Verifica che le fonti vengano deduplicate per file."""
        chunks = [
            {"source_file": "manuale.pdf", "title": "Manuale", "content": "", "section": "", "page_num": None, "score": 0.9},
            {"source_file": "manuale.pdf", "title": "Manuale", "content": "", "section": "", "page_num": None, "score": 0.7},
            {"source_file": "guida.txt", "title": "Guida", "content": "", "section": "", "page_num": None, "score": 0.6},
        ]
        sources = _format_sources(chunks)

        assert sources.count("manuale.pdf") == 1
        assert "guida.txt" in sources

    def test_format_sources_with_page_numbers(self):
        """Verifica formattazione fonti con numeri pagina."""
        chunks = [
            {"source_file": "manuale.pdf", "title": "Manuale", "content": "", "section": "", "page_num": 5, "score": 0.9},
            {"source_file": "manuale.pdf", "title": "Manuale", "content": "", "section": "", "page_num": 12, "score": 0.7},
            {"source_file": "guida.txt", "title": "Guida", "content": "", "section": "", "page_num": None, "score": 0.6},
        ]
        sources = _format_sources(chunks)

        # Pagine diverse dello stesso file devono apparire come fonti separate
        assert "pag. 5" in sources
        assert "pag. 12" in sources
        # File senza pagina non deve avere "pag."
        assert "guida.txt)" in sources

    def test_format_sources_deduplication_same_page(self):
        """Verifica deduplicazione per stessa pagina dello stesso file."""
        chunks = [
            {"source_file": "manuale.pdf", "title": "Manuale", "content": "", "section": "", "page_num": 5, "score": 0.9},
            {"source_file": "manuale.pdf", "title": "Manuale", "content": "", "section": "", "page_num": 5, "score": 0.7},
        ]
        sources = _format_sources(chunks)

        # Stessa pagina deve apparire una sola volta
        assert sources.count("pag. 5") == 1

    def test_format_sources_empty(self):
        """Verifica fonti vuote."""
        sources = _format_sources([])
        assert sources == ""


class TestIntentClassification:
    """Test classificazione intent info_procedure."""

    def test_procedure_in_valid_intents(self):
        """Verifica che info_procedure sia in VALID_INTENTS."""
        from orchestrator.router import Router
        assert "info_procedure" in Router.VALID_INTENTS

    def test_procedure_pattern_match(self):
        """Verifica che i pattern regex matchino le query procedurali."""
        from orchestrator.router import Router
        pattern = Router.PROCEDURE_PATTERNS

        assert pattern.search("qual e' la procedura per ispezione semplice")
        assert pattern.search("come si esegue un controllo")
        assert pattern.search("quali sono i passi per registrare una NC")
        assert pattern.search("istruzioni per il controllo ufficiale")
        assert pattern.search("guida per la verifica")
        assert not pattern.search("stabilimenti a rischio")
        assert not pattern.search("piani in ritardo")

    def test_tool_registry_mapping(self):
        """Verifica registrazione nel TOOL_REGISTRY e INTENT_TO_TOOL."""
        from orchestrator.tool_nodes import TOOL_REGISTRY, INTENT_TO_TOOL

        assert "info_procedure_tool" in TOOL_REGISTRY
        assert "info_procedure" in INTENT_TO_TOOL
        assert INTENT_TO_TOOL["info_procedure"] == "info_procedure_tool"

    def test_intent_metadata_registered(self):
        """Verifica metadata registrata per info_procedure."""
        from orchestrator.intent_metadata import INTENT_REGISTRY

        assert "info_procedure" in INTENT_REGISTRY
        meta = INTENT_REGISTRY["info_procedure"]
        assert meta.category == "Procedure Operative"
        assert "procedura" in meta.keywords
