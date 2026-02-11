#!/usr/bin/env python3
"""
Document chunker per il sistema RAG.

Carica documenti (PDF, DOCX, TXT) e li spezza in chunk indicizzabili
con metadata (source_file, title, section, chunk_index, page_num).

Usage:
    from tools.indexing.doc_chunker import DocumentChunker
    chunker = DocumentChunker(chunk_size=600, chunk_overlap=100)
    chunks = chunker.process_directory("data/documents/")
"""

import os
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Regex per rilevare header di sezione
# Markdown headers: ## Titolo, ### Sottotitolo
RE_MARKDOWN_HEADER = re.compile(r'^#{1,4}\s+(.+)$', re.MULTILINE)
# Titoli in maiuscolo (almeno 3 parole, tutto caps)
RE_CAPS_HEADER = re.compile(r'^([A-Z][A-Z\s\d\.\-\':]{10,})$', re.MULTILINE)
# Header numerati: 1. Titolo, 1.2 Titolo, Art. 3
RE_NUMBERED_HEADER = re.compile(
    r'^(?:(?:Art\.?\s*)?(\d+(?:\.\d+)*)[\.)\s]+\s*)([A-Z].{5,})$',
    re.MULTILINE
)


class DocumentChunker:
    """
    Carica e spezza documenti in chunk per indicizzazione vettoriale.

    Supporta PDF, DOCX e TXT. Preserva metadata di sezione
    per migliorare la qualita' del retrieval.
    """

    SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}

    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        """
        Args:
            chunk_size: Dimensione target di ogni chunk in caratteri.
            chunk_overlap: Sovrapposizione tra chunk consecutivi.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_directory(self, dir_path: str) -> List[Dict]:
        """
        Processa tutti i documenti supportati in una directory.

        Args:
            dir_path: Path alla directory con i documenti.

        Returns:
            Lista di chunk con content + metadata.
        """
        if not os.path.isdir(dir_path):
            logger.error(f"Directory non trovata: {dir_path}")
            return []

        all_chunks = []
        files = sorted(os.listdir(dir_path))

        for filename in files:
            filepath = os.path.join(dir_path, filename)
            if not os.path.isfile(filepath):
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in self.SUPPORTED_EXTENSIONS:
                logger.debug(f"File ignorato (estensione non supportata): {filename}")
                continue

            try:
                chunks = self.load_file(filepath)
                all_chunks.extend(chunks)
                logger.info(f"Processato {filename}: {len(chunks)} chunk")
            except Exception as e:
                logger.error(f"Errore processando {filename}: {e}")

        logger.info(f"Totale: {len(all_chunks)} chunk da {len(files)} file")
        return all_chunks

    def load_file(self, filepath: str) -> List[Dict]:
        """
        Carica un file e restituisce i chunk con metadata.

        Args:
            filepath: Path al file da caricare.

        Returns:
            Lista di chunk dict con 'content' e 'metadata'.
        """
        ext = os.path.splitext(filepath)[1].lower()
        filename = os.path.basename(filepath)
        title = self._extract_title_from_filename(filename)

        loaders = {
            '.pdf': self._load_pdf,
            '.docx': self._load_docx,
            '.txt': self._load_txt,
            '.md': self._load_txt,
        }

        loader = loaders.get(ext)
        if not loader:
            raise ValueError(f"Estensione non supportata: {ext}")

        text, page_map = loader(filepath)

        if not text or not text.strip():
            logger.warning(f"File vuoto o illeggibile: {filepath}")
            return []

        base_metadata = {
            "source_file": filename,
            "title": title,
        }

        chunks = self.chunk_text(text, base_metadata, page_map=page_map)
        return chunks

    def _load_pdf(self, filepath: str) -> tuple:
        """
        Estrae testo da PDF con PyMuPDF.

        Returns:
            (testo_completo, page_map) dove page_map mappa offset_carattere -> numero_pagina
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF richiesto per PDF. Installa con: pip install PyMuPDF"
            )

        doc = fitz.open(filepath)
        full_text = ""
        page_map = {}  # char_offset -> page_num

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text:
                offset = len(full_text)
                page_map[offset] = page_num + 1  # 1-indexed
                full_text += page_text + "\n\n"

        doc.close()
        return full_text, page_map

    def _load_docx(self, filepath: str) -> tuple:
        """Estrae testo da DOCX con python-docx."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError(
                "python-docx richiesto per DOCX. Installa con: pip install python-docx"
            )

        doc = Document(filepath)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        full_text = "\n\n".join(paragraphs)
        return full_text, {}

    def _load_txt(self, filepath: str) -> tuple:
        """Legge file di testo."""
        encodings = ['utf-8', 'latin-1', 'cp1252']
        for enc in encodings:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    return f.read(), {}
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Impossibile leggere {filepath} con encoding supportati")

    def chunk_text(
        self,
        text: str,
        base_metadata: Dict,
        page_map: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Splitta testo in chunk con overlap, preservando paragrafi e sezioni.

        Args:
            text: Testo completo del documento.
            base_metadata: Metadata di base (source_file, title).
            page_map: Opzionale mappa offset -> page_num (per PDF).

        Returns:
            Lista di chunk dict con 'content' e 'metadata'.
        """
        # Estrai header di sezione con posizioni
        section_headers = self._extract_section_headers(text)

        # Splitta per paragrafi
        paragraphs = self._split_into_paragraphs(text)

        chunks = []
        current_chunk = ""
        current_section = ""
        char_offset = 0

        for para in paragraphs:
            para_stripped = para.strip()
            if not para_stripped:
                char_offset += len(para) + 2  # +2 per \n\n
                continue

            # Aggiorna sezione corrente
            new_section = self._find_section_at_offset(
                section_headers, char_offset
            )
            if new_section:
                current_section = new_section

            # Se aggiungere il paragrafo supera chunk_size, chiudi il chunk
            if current_chunk and len(current_chunk) + len(para_stripped) + 1 > self.chunk_size:
                chunk_meta = {**base_metadata, "section": current_section}
                if page_map:
                    chunk_meta["page_num"] = self._get_page_num(
                        page_map, char_offset - len(current_chunk)
                    )
                chunks.append({
                    "content": current_chunk.strip(),
                    "metadata": chunk_meta
                })

                # Overlap: mantieni gli ultimi chunk_overlap caratteri
                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    current_chunk = current_chunk[-self.chunk_overlap:]
                else:
                    current_chunk = ""

            # Se il paragrafo stesso e' piu' lungo del chunk_size, spezzalo per frasi
            if len(para_stripped) > self.chunk_size:
                sentences = self._split_into_sentences(para_stripped)
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 > self.chunk_size and current_chunk:
                        chunk_meta = {**base_metadata, "section": current_section}
                        if page_map:
                            chunk_meta["page_num"] = self._get_page_num(
                                page_map, char_offset
                            )
                        chunks.append({
                            "content": current_chunk.strip(),
                            "metadata": chunk_meta
                        })
                        if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                            current_chunk = current_chunk[-self.chunk_overlap:]
                        else:
                            current_chunk = ""
                    current_chunk += " " + sent if current_chunk else sent
            else:
                current_chunk += "\n\n" + para_stripped if current_chunk else para_stripped

            char_offset += len(para) + 2

        # Ultimo chunk
        if current_chunk.strip():
            chunk_meta = {**base_metadata, "section": current_section}
            if page_map:
                chunk_meta["page_num"] = self._get_page_num(
                    page_map, char_offset - len(current_chunk)
                )
            chunks.append({
                "content": current_chunk.strip(),
                "metadata": chunk_meta
            })

        # Aggiungi chunk_index e total_chunks
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i
            chunk["metadata"]["total_chunks"] = total

        return chunks

    def _extract_section_headers(self, text: str) -> List[Dict]:
        """
        Estrae header di sezione con le loro posizioni nel testo.

        Returns:
            Lista ordinata di {"offset": int, "title": str}
        """
        headers = []

        for pattern in [RE_MARKDOWN_HEADER, RE_CAPS_HEADER, RE_NUMBERED_HEADER]:
            for match in pattern.finditer(text):
                # Per RE_NUMBERED_HEADER il titolo e' nel gruppo 2
                if pattern == RE_NUMBERED_HEADER:
                    title = match.group(2).strip() if match.group(2) else match.group(0).strip()
                else:
                    title = match.group(1).strip() if match.lastindex else match.group(0).strip()

                headers.append({
                    "offset": match.start(),
                    "title": title[:100]  # Limita lunghezza
                })

        headers.sort(key=lambda h: h["offset"])
        return headers

    def _find_section_at_offset(
        self,
        headers: List[Dict],
        offset: int
    ) -> Optional[str]:
        """Trova l'header di sezione piu' vicino prima dell'offset dato."""
        current = None
        for h in headers:
            if h["offset"] <= offset:
                current = h["title"]
            else:
                break
        return current

    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Splitta testo in paragrafi (separati da doppio newline)."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p for p in paragraphs if p.strip()]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splitta testo in frasi."""
        # Split su punto/punto e virgola/punto esclamativo/punto interrogativo
        # seguito da spazio e lettera maiuscola
        sentences = re.split(r'(?<=[.!?;])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_page_num(self, page_map: Dict, offset: int) -> Optional[int]:
        """Trova il numero di pagina per un dato offset nel testo."""
        if not page_map:
            return None
        current_page = 1
        for page_offset, page_num in sorted(page_map.items()):
            if page_offset <= offset:
                current_page = page_num
            else:
                break
        return current_page

    def _extract_title_from_filename(self, filename: str) -> str:
        """Estrae un titolo leggibile dal nome del file."""
        name = os.path.splitext(filename)[0]
        # Sostituisci underscore e trattini con spazi
        name = name.replace('_', ' ').replace('-', ' ')
        # Capitalizza
        return name.strip().title()
