"""Text chunking service for creating overlapping chunks for RAG system."""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    tiktoken = None
    HAS_TIKTOKEN = False

from app.utils.exceptions import ProcessingError


logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for text chunking."""
    chunk_size: int = 1000  # Maximum tokens per chunk
    overlap: int = 200      # Tokens to overlap between chunks
    min_chunk_size: int = 100  # Minimum tokens for a valid chunk
    preserve_sentences: bool = True  # Try to break at sentence boundaries
    preserve_paragraphs: bool = True  # Try to break at paragraph boundaries


class TextChunker:
    """Service for chunking text into overlapping segments for RAG processing."""
    
    # Default encoding for token counting
    DEFAULT_ENCODING = "cl100k_base"  # GPT-3.5/4 encoding
    
    # Sentence boundary patterns
    SENTENCE_ENDINGS = re.compile(r'[.!?]+\s+')
    PARAGRAPH_BREAKS = re.compile(r'\n\s*\n')
    
    def __init__(self, config: ChunkConfig = None):
        """
        Initialize text chunker.
        
        Args:
            config: Chunking configuration
        """
        self.config = config or ChunkConfig()
        
        # Initialize tokenizer
        if HAS_TIKTOKEN:
            try:
                self.encoding = tiktoken.get_encoding(self.DEFAULT_ENCODING)
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding: {str(e)}")
                self.encoding = None
        else:
            logger.warning("tiktoken not available, using word-based approximation")
            self.encoding = None
    
    def chunk_text(self, text: str, config: ChunkConfig = None) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            config: Optional chunking configuration (overrides instance config)
            
        Returns:
            List of chunk dictionaries with content, position, and metadata
        """
        try:
            chunk_config = config or self.config
            
            # Validate configuration
            if chunk_config.overlap >= chunk_config.chunk_size:
                raise ProcessingError("Overlap must be less than chunk size")
            
            if chunk_config.chunk_size < chunk_config.min_chunk_size:
                raise ProcessingError("Chunk size must be at least min_chunk_size")
            
            # Clean and normalize text
            text = self._normalize_text(text)
            
            if not text.strip():
                return []
            
            # Count total tokens
            total_tokens = self._count_tokens(text)
            
            # If text fits in single chunk, return as-is
            if total_tokens <= chunk_config.chunk_size:
                chunk = {
                    'content': text,
                    'position': 0,
                    'token_count': total_tokens,
                    'overlap_start': 0,
                    'overlap_end': 0,
                    'chunk_type': 'single',
                    'chunk_index': 0,
                    'is_first': True,
                    'is_last': True
                }
                return [chunk]
            
            # Choose chunking strategy based on configuration
            if chunk_config.preserve_paragraphs:
                chunks = self._chunk_by_paragraphs(text, chunk_config)
            elif chunk_config.preserve_sentences:
                chunks = self._chunk_by_sentences(text, chunk_config)
            else:
                chunks = self._chunk_by_tokens(text, chunk_config)
            
            # Post-process chunks
            chunks = self._post_process_chunks(chunks, chunk_config)
            
            return chunks
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to chunk text: {str(e)}")
            raise ProcessingError(f"Failed to chunk text: {str(e)}")
    
    def chunk_document_content(self, content: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Chunk document content with document-specific optimizations.
        
        Args:
            content: Document content to chunk
            metadata: Document metadata for context-aware chunking
            
        Returns:
            List of chunk dictionaries
        """
        try:
            # Create document-specific chunking config
            config = self._create_document_config(metadata or {})
            
            # Chunk the content
            chunks = self.chunk_text(content, config)
            
            # Add document-specific metadata to chunks
            for i, chunk in enumerate(chunks):
                chunk['document_metadata'] = metadata
                chunk['chunk_id'] = f"chunk_{i}"
                
                # Add content type specific metadata
                if metadata:
                    chunk['source_type'] = metadata.get('format', 'unknown')
                    chunk['source_title'] = metadata.get('title', '')
            
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to chunk document content: {str(e)}")
            raise ProcessingError(f"Failed to chunk document content: {str(e)}")
    
    def _chunk_by_paragraphs(self, text: str, config: ChunkConfig) -> List[Dict[str, Any]]:
        """Chunk text by paragraphs, respecting token limits."""
        paragraphs = self.PARAGRAPH_BREAKS.split(text)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        position = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            para_tokens = self._count_tokens(paragraph)
            
            # If paragraph alone exceeds chunk size, split it further
            if para_tokens > config.chunk_size:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk, position, current_tokens, config
                    ))
                    position += 1
                    current_chunk = ""
                    current_tokens = 0
                
                # Split large paragraph by sentences
                para_chunks = self._chunk_by_sentences(paragraph, config)
                for para_chunk in para_chunks:
                    para_chunk['position'] = position
                    chunks.append(para_chunk)
                    position += 1
                
            # If adding paragraph would exceed limit, save current chunk
            elif current_tokens + para_tokens > config.chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk, position, current_tokens, config
                ))
                position += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, config.overlap)
                current_chunk = overlap_text + "\n\n" + paragraph if overlap_text else paragraph
                current_tokens = self._count_tokens(current_chunk)
                
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
                current_tokens = self._count_tokens(current_chunk)
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                current_chunk, position, current_tokens, config
            ))
        
        return chunks
    
    def _chunk_by_sentences(self, text: str, config: ChunkConfig) -> List[Dict[str, Any]]:
        """Chunk text by sentences, respecting token limits."""
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = ""
        current_tokens = 0
        position = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_tokens = self._count_tokens(sentence)
            
            # If sentence alone exceeds chunk size, split by tokens
            if sentence_tokens > config.chunk_size:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(self._create_chunk(
                        current_chunk, position, current_tokens, config
                    ))
                    position += 1
                    current_chunk = ""
                    current_tokens = 0
                
                # Split large sentence by tokens
                sentence_chunks = self._chunk_by_tokens(sentence, config)
                for sent_chunk in sentence_chunks:
                    sent_chunk['position'] = position
                    chunks.append(sent_chunk)
                    position += 1
                
            # If adding sentence would exceed limit, save current chunk
            elif current_tokens + sentence_tokens > config.chunk_size and current_chunk:
                chunks.append(self._create_chunk(
                    current_chunk, position, current_tokens, config
                ))
                position += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, config.overlap)
                current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                current_tokens = self._count_tokens(current_chunk)
                
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_tokens = self._count_tokens(current_chunk)
        
        # Add final chunk
        if current_chunk:
            chunks.append(self._create_chunk(
                current_chunk, position, current_tokens, config
            ))
        
        return chunks
    
    def _chunk_by_tokens(self, text: str, config: ChunkConfig) -> List[Dict[str, Any]]:
        """Chunk text by token count with overlap."""
        if not self.encoding:
            # Fallback to word-based chunking
            return self._chunk_by_words(text, config)
        
        tokens = self.encoding.encode(text)
        chunks = []
        position = 0
        chunk_index = 0
        
        while position < len(tokens):
            # Calculate chunk boundaries
            end_position = min(position + config.chunk_size, len(tokens))
            
            # Extract chunk tokens
            chunk_tokens = tokens[position:end_position]
            
            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)
            
            # Calculate overlap information
            overlap_start = config.overlap if chunk_index > 0 else 0
            overlap_end = config.overlap if end_position < len(tokens) else 0
            
            chunks.append({
                'content': chunk_text,
                'position': chunk_index,
                'token_count': len(chunk_tokens),
                'overlap_start': overlap_start,
                'overlap_end': overlap_end,
                'chunk_type': 'token_based'
            })
            
            # Move position forward (accounting for overlap)
            position = end_position - config.overlap
            chunk_index += 1
            
            # Prevent infinite loop
            if position <= 0:
                break
        
        return chunks
    
    def _chunk_by_words(self, text: str, config: ChunkConfig) -> List[Dict[str, Any]]:
        """Fallback word-based chunking when tokenizer is not available."""
        words = text.split()
        
        # Estimate tokens per word (rough approximation)
        tokens_per_word = 1.3
        words_per_chunk = int(config.chunk_size / tokens_per_word)
        overlap_words = int(config.overlap / tokens_per_word)
        
        chunks = []
        position = 0
        chunk_index = 0
        
        while position < len(words):
            # Calculate chunk boundaries
            end_position = min(position + words_per_chunk, len(words))
            
            # Extract chunk words
            chunk_words = words[position:end_position]
            chunk_text = ' '.join(chunk_words)
            
            # Estimate token count
            estimated_tokens = int(len(chunk_words) * tokens_per_word)
            
            # Calculate overlap information
            overlap_start = overlap_words if chunk_index > 0 else 0
            overlap_end = overlap_words if end_position < len(words) else 0
            
            chunks.append({
                'content': chunk_text,
                'position': chunk_index,
                'token_count': estimated_tokens,
                'overlap_start': overlap_start,
                'overlap_end': overlap_end,
                'chunk_type': 'word_based'
            })
            
            # Move position forward (accounting for overlap)
            position = end_position - overlap_words
            chunk_index += 1
            
            # Prevent infinite loop
            if position <= 0:
                break
        
        return chunks
    
    def _create_chunk(self, content: str, position: int, token_count: int, config: ChunkConfig) -> Dict[str, Any]:
        """Create a chunk dictionary."""
        return {
            'content': content.strip(),
            'position': position,
            'token_count': token_count,
            'overlap_start': config.overlap if position > 0 else 0,
            'overlap_end': config.overlap,  # Will be adjusted in post-processing
            'chunk_type': 'semantic'
        }
    
    def _post_process_chunks(self, chunks: List[Dict[str, Any]], config: ChunkConfig) -> List[Dict[str, Any]]:
        """Post-process chunks to clean up and validate."""
        processed_chunks = []
        
        for i, chunk in enumerate(chunks):
            # Skip chunks that are too small
            if chunk['token_count'] < config.min_chunk_size:
                logger.debug(f"Skipping chunk {i} - too small ({chunk['token_count']} tokens)")
                continue
            
            # Adjust overlap_end for last chunk
            if i == len(chunks) - 1:
                chunk['overlap_end'] = 0
            
            # Clean content
            chunk['content'] = self._clean_chunk_content(chunk['content'])
            
            # Recalculate token count after cleaning
            chunk['token_count'] = self._count_tokens(chunk['content'])
            
            # Add chunk metadata
            chunk['chunk_index'] = len(processed_chunks)
            chunk['is_first'] = len(processed_chunks) == 0
            chunk['is_last'] = i == len(chunks) - 1
            
            processed_chunks.append(chunk)
        
        return processed_chunks
    
    def _create_document_config(self, metadata: Dict[str, Any]) -> ChunkConfig:
        """Create document-specific chunking configuration."""
        config = ChunkConfig()
        
        # Adjust based on document type
        doc_format = metadata.get('format', '').lower()
        
        if doc_format == 'pdf':
            # PDFs often have formatting issues, use smaller chunks
            config.chunk_size = 800
            config.overlap = 150
            config.preserve_sentences = True
            config.preserve_paragraphs = False
            
        elif doc_format == 'html':
            # HTML content can be noisy, use paragraph-based chunking
            config.chunk_size = 1200
            config.overlap = 200
            config.preserve_paragraphs = True
            
        elif doc_format == 'markdown':
            # Markdown has good structure, preserve it
            config.chunk_size = 1000
            config.overlap = 200
            config.preserve_paragraphs = True
            
        elif doc_format == 'plain_text':
            # Plain text, use sentence-based chunking
            config.chunk_size = 1000
            config.overlap = 200
            config.preserve_sentences = True
            
        # Adjust based on content length
        total_tokens = metadata.get('token_count', 0)
        if total_tokens > 10000:
            # For very long documents, use larger chunks
            config.chunk_size = min(1500, config.chunk_size * 1.5)
        
        return config
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent chunking."""
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Normalize line breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove excessive spaces
        text = re.sub(r' {3,}', '  ', text)
        
        return text.strip()
    
    def _clean_chunk_content(self, content: str) -> str:
        """Clean chunk content."""
        if not content:
            return ""
        
        # Remove leading/trailing whitespace
        content = content.strip()
        
        # Remove empty lines at start/end
        lines = content.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        return '\n'.join(lines)
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - could be improved with NLTK
        sentences = self.SENTENCE_ENDINGS.split(text)
        
        # Clean up sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def _get_overlap_text(self, text: str, overlap_tokens: int) -> str:
        """Get overlap text from the end of a chunk."""
        if not text or overlap_tokens <= 0:
            return ""
        
        if self.encoding:
            tokens = self.encoding.encode(text)
            if len(tokens) <= overlap_tokens:
                return text
            
            overlap_tokens_list = tokens[-overlap_tokens:]
            return self.encoding.decode(overlap_tokens_list)
        else:
            # Fallback to word-based overlap
            words = text.split()
            overlap_words = int(overlap_tokens / 1.3)  # Rough conversion
            
            if len(words) <= overlap_words:
                return text
            
            return ' '.join(words[-overlap_words:])
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        
        if HAS_TIKTOKEN and self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception:
                pass
        
        # Fallback to word count * 1.3
        return int(len(text.split()) * 1.3)
    
    def get_chunk_statistics(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about chunks."""
        if not chunks:
            return {
                'total_chunks': 0,
                'total_tokens': 0,
                'avg_tokens_per_chunk': 0,
                'min_tokens': 0,
                'max_tokens': 0
            }
        
        token_counts = [chunk['token_count'] for chunk in chunks]
        
        return {
            'total_chunks': len(chunks),
            'total_tokens': sum(token_counts),
            'avg_tokens_per_chunk': sum(token_counts) / len(token_counts),
            'min_tokens': min(token_counts),
            'max_tokens': max(token_counts),
            'chunk_types': list(set(chunk.get('chunk_type', 'unknown') for chunk in chunks))
        }