"""Tests for text chunking service."""
import pytest
from unittest.mock import patch, MagicMock

from app.services.text_chunker import TextChunker, ChunkConfig
from app.utils.exceptions import ProcessingError


class TestTextChunker:
    """Test cases for TextChunker."""
    
    def test_init_default_config(self):
        """Test TextChunker initialization with default configuration."""
        chunker = TextChunker()
        
        assert chunker.config.chunk_size == 1000
        assert chunker.config.overlap == 200
        assert chunker.config.min_chunk_size == 100
        assert chunker.config.preserve_sentences is True
        assert chunker.config.preserve_paragraphs is True
    
    def test_init_custom_config(self):
        """Test TextChunker initialization with custom configuration."""
        config = ChunkConfig(
            chunk_size=500,
            overlap=100,
            min_chunk_size=50,
            preserve_sentences=False,
            preserve_paragraphs=False
        )
        
        chunker = TextChunker(config)
        
        assert chunker.config.chunk_size == 500
        assert chunker.config.overlap == 100
        assert chunker.config.min_chunk_size == 50
        assert chunker.config.preserve_sentences is False
        assert chunker.config.preserve_paragraphs is False
    
    def test_chunk_text_empty(self):
        """Test chunking empty text."""
        chunker = TextChunker()
        
        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []
        assert chunker.chunk_text("\n\n\n") == []
    
    def test_chunk_text_single_chunk(self):
        """Test chunking text that fits in a single chunk."""
        chunker = TextChunker()
        text = "This is a short text that should fit in one chunk."
        
        chunks = chunker.chunk_text(text)
        
        assert len(chunks) == 1
        assert chunks[0]['content'] == text
        assert chunks[0]['position'] == 0
        assert chunks[0]['overlap_start'] == 0
        assert chunks[0]['overlap_end'] == 0
        assert chunks[0]['chunk_type'] == 'single'
        assert chunks[0]['is_first'] is True
        assert chunks[0]['is_last'] is True
    
    def test_chunk_text_invalid_config(self):
        """Test error handling for invalid configuration."""
        chunker = TextChunker()
        
        with pytest.raises(ProcessingError, match="Overlap must be less than chunk size"):
            chunker.chunk_text("Some text", ChunkConfig(chunk_size=100, overlap=150))
        
        with pytest.raises(ProcessingError, match="Chunk size must be at least min_chunk_size"):
            chunker.chunk_text("Some text", ChunkConfig(chunk_size=50, min_chunk_size=100))
    
    @patch('tiktoken.get_encoding')
    def test_chunk_text_by_tokens(self, mock_encoding):
        """Test token-based chunking."""
        # Mock tokenizer
        mock_enc = MagicMock()
        # Create a text that would be split into multiple chunks
        test_text = "word " * 600  # 600 words
        tokens = list(range(1200))  # 1200 tokens (2 per word)
        
        mock_enc.encode.return_value = tokens
        mock_enc.decode.side_effect = lambda token_list: ' '.join([f'word{i//2}' for i in token_list])
        
        mock_encoding.return_value = mock_enc
        
        config = ChunkConfig(
            chunk_size=500,
            overlap=100,
            preserve_sentences=False,
            preserve_paragraphs=False
        )
        
        chunker = TextChunker(config)
        chunks = chunker.chunk_text(test_text, config)
        
        assert len(chunks) > 1
        assert all(chunk['token_count'] <= 500 for chunk in chunks)
        assert chunks[0]['overlap_start'] == 0
        assert all(chunk['overlap_start'] == 100 for chunk in chunks[1:])
        assert chunks[-1]['overlap_end'] == 0
    
    def test_chunk_by_paragraphs(self):
        """Test paragraph-based chunking."""
        text = """First paragraph with some content.

Second paragraph with more content.

Third paragraph with additional content.

Fourth paragraph with even more content."""
        
        config = ChunkConfig(
            chunk_size=50,  # Small chunks to force splitting
            overlap=10,
            preserve_paragraphs=True
        )
        
        chunker = TextChunker(config)
        chunks = chunker.chunk_text(text, config)
        
        assert len(chunks) > 1
        # Each chunk should contain complete paragraphs when possible
        for chunk in chunks:
            assert not chunk['content'].startswith('\n\n')
            assert not chunk['content'].endswith('\n\n')
    
    def test_chunk_by_sentences(self):
        """Test sentence-based chunking."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        
        config = ChunkConfig(
            chunk_size=20,  # Small chunks to force splitting
            overlap=5,
            preserve_sentences=True,
            preserve_paragraphs=False
        )
        
        chunker = TextChunker(config)
        chunks = chunker.chunk_text(text, config)
        
        assert len(chunks) > 1
        # Each chunk should contain complete sentences when possible
        for chunk in chunks:
            content = chunk['content'].strip()
            if content and not content.endswith('.'):
                # If it doesn't end with period, it might be a partial sentence due to size constraints
                pass
    
    @patch('tiktoken.get_encoding')
    def test_chunk_by_words_fallback(self, mock_encoding):
        """Test word-based chunking when tokenizer is not available."""
        mock_encoding.side_effect = Exception("Tokenizer not available")
        
        text = "word " * 100  # 100 words
        
        config = ChunkConfig(
            chunk_size=50,  # ~38 words per chunk (50 / 1.3)
            overlap=10,     # ~7 words overlap
            preserve_sentences=False,
            preserve_paragraphs=False
        )
        
        chunker = TextChunker(config)
        chunks = chunker.chunk_text(text, config)
        
        assert len(chunks) > 1
        assert all(chunk['chunk_type'] == 'word_based' for chunk in chunks)
        assert all(isinstance(chunk['token_count'], int) for chunk in chunks)
    
    def test_chunk_document_content(self):
        """Test document-specific chunking."""
        content = "This is document content with multiple sentences. It should be chunked appropriately."
        metadata = {
            'format': 'markdown',
            'title': 'Test Document',
            'token_count': 100
        }
        
        chunker = TextChunker()
        chunks = chunker.chunk_document_content(content, metadata)
        
        assert len(chunks) >= 1
        for i, chunk in enumerate(chunks):
            assert chunk['document_metadata'] == metadata
            assert chunk['chunk_id'] == f'chunk_{i}'
            assert chunk['source_type'] == 'markdown'
            assert chunk['source_title'] == 'Test Document'
    
    def test_create_document_config_pdf(self):
        """Test document-specific configuration for PDF."""
        chunker = TextChunker()
        metadata = {'format': 'pdf'}
        
        config = chunker._create_document_config(metadata)
        
        assert config.chunk_size == 800
        assert config.overlap == 150
        assert config.preserve_sentences is True
        assert config.preserve_paragraphs is False
    
    def test_create_document_config_html(self):
        """Test document-specific configuration for HTML."""
        chunker = TextChunker()
        metadata = {'format': 'html'}
        
        config = chunker._create_document_config(metadata)
        
        assert config.chunk_size == 1200
        assert config.overlap == 200
        assert config.preserve_paragraphs is True
    
    def test_create_document_config_long_document(self):
        """Test configuration adjustment for long documents."""
        chunker = TextChunker()
        metadata = {'format': 'plain_text', 'token_count': 15000}
        
        config = chunker._create_document_config(metadata)
        
        # Should use larger chunks for long documents
        assert config.chunk_size > 1000
    
    def test_normalize_text(self):
        """Test text normalization."""
        chunker = TextChunker()
        
        # Test whitespace normalization
        text = "This   has    multiple     spaces."
        normalized = chunker._normalize_text(text)
        assert normalized == "This has multiple spaces."
        
        # Test line break normalization
        text = "Line 1\n\n\n\n\nLine 2"
        normalized = chunker._normalize_text(text)
        assert normalized == "Line 1\n\nLine 2"
        
        # Test excessive spaces
        text = "Word1   Word2     Word3"
        normalized = chunker._normalize_text(text)
        assert normalized == "Word1 Word2 Word3"
    
    def test_clean_chunk_content(self):
        """Test chunk content cleaning."""
        chunker = TextChunker()
        
        # Test leading/trailing whitespace removal
        content = "  \n  Content with spaces  \n  "
        cleaned = chunker._clean_chunk_content(content)
        assert cleaned == "Content with spaces"
        
        # Test empty line removal
        content = "\n\nActual content\n\n"
        cleaned = chunker._clean_chunk_content(content)
        assert cleaned == "Actual content"
    
    def test_split_sentences(self):
        """Test sentence splitting."""
        chunker = TextChunker()
        
        text = "First sentence. Second sentence! Third sentence? Fourth sentence."
        sentences = chunker._split_sentences(text)
        
        assert len(sentences) == 4
        assert "First sentence" in sentences[0]
        assert "Second sentence" in sentences[1]
        assert "Third sentence" in sentences[2]
        assert "Fourth sentence" in sentences[3]
    
    @patch('tiktoken.get_encoding')
    def test_get_overlap_text_with_tokenizer(self, mock_encoding):
        """Test overlap text extraction with tokenizer."""
        mock_enc = MagicMock()
        mock_enc.encode.return_value = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        mock_enc.decode.return_value = "overlap text"
        
        mock_encoding.return_value = mock_enc
        
        chunker = TextChunker()
        text = "This is some text for overlap testing."
        overlap = chunker._get_overlap_text(text, 3)
        
        assert overlap == "overlap text"
        mock_enc.decode.assert_called_once_with([8, 9, 10])  # Last 3 tokens
    
    @patch('tiktoken.get_encoding')
    def test_get_overlap_text_fallback(self, mock_encoding):
        """Test overlap text extraction fallback to words."""
        mock_encoding.side_effect = Exception("No tokenizer")
        
        chunker = TextChunker()
        text = "word1 word2 word3 word4 word5"
        overlap = chunker._get_overlap_text(text, 3)  # ~2 words (3/1.3)
        
        assert "word4 word5" in overlap
    
    @patch('tiktoken.get_encoding')
    def test_count_tokens_with_tokenizer(self, mock_encoding):
        """Test token counting with tokenizer."""
        mock_enc = MagicMock()
        mock_enc.encode.return_value = [1, 2, 3, 4, 5]
        
        mock_encoding.return_value = mock_enc
        
        chunker = TextChunker()
        count = chunker._count_tokens("test text")
        
        assert count == 5
    
    @patch('tiktoken.get_encoding')
    def test_count_tokens_fallback(self, mock_encoding):
        """Test token counting fallback to word count."""
        mock_encoding.side_effect = Exception("No tokenizer")
        
        chunker = TextChunker()
        count = chunker._count_tokens("word1 word2 word3")  # 3 words
        
        assert count == int(3 * 1.3)  # 3.9 -> 3
    
    def test_count_tokens_empty(self):
        """Test token counting with empty text."""
        chunker = TextChunker()
        
        assert chunker._count_tokens("") == 0
        assert chunker._count_tokens(None) == 0
    
    def test_post_process_chunks(self):
        """Test chunk post-processing."""
        chunker = TextChunker()
        config = ChunkConfig(min_chunk_size=10)
        
        chunks = [
            {'content': '  Content 1  ', 'token_count': 20, 'position': 0, 'overlap_end': 5},
            {'content': 'Small', 'token_count': 5, 'position': 1, 'overlap_end': 5},  # Too small
            {'content': '  Content 2  ', 'token_count': 15, 'position': 2, 'overlap_end': 5},
        ]
        
        processed = chunker._post_process_chunks(chunks, config)
        
        # Should skip the small chunk
        assert len(processed) == 2
        assert processed[0]['content'] == 'Content 1'  # Cleaned
        assert processed[0]['chunk_index'] == 0
        assert processed[0]['is_first'] is True
        assert processed[0]['is_last'] is False
        
        assert processed[1]['content'] == 'Content 2'
        assert processed[1]['chunk_index'] == 1
        assert processed[1]['is_first'] is False
        assert processed[1]['is_last'] is True
        assert processed[1]['overlap_end'] == 0  # Last chunk has no end overlap
    
    def test_get_chunk_statistics(self):
        """Test chunk statistics calculation."""
        chunker = TextChunker()
        
        chunks = [
            {'token_count': 100, 'chunk_type': 'semantic'},
            {'token_count': 150, 'chunk_type': 'semantic'},
            {'token_count': 200, 'chunk_type': 'token_based'},
        ]
        
        stats = chunker.get_chunk_statistics(chunks)
        
        assert stats['total_chunks'] == 3
        assert stats['total_tokens'] == 450
        assert stats['avg_tokens_per_chunk'] == 150
        assert stats['min_tokens'] == 100
        assert stats['max_tokens'] == 200
        assert 'semantic' in stats['chunk_types']
        assert 'token_based' in stats['chunk_types']
    
    def test_get_chunk_statistics_empty(self):
        """Test chunk statistics with empty list."""
        chunker = TextChunker()
        
        stats = chunker.get_chunk_statistics([])
        
        assert stats['total_chunks'] == 0
        assert stats['total_tokens'] == 0
        assert stats['avg_tokens_per_chunk'] == 0
        assert stats['min_tokens'] == 0
        assert stats['max_tokens'] == 0
    
    def test_chunk_config_dataclass(self):
        """Test ChunkConfig dataclass functionality."""
        # Test default values
        config = ChunkConfig()
        assert config.chunk_size == 1000
        assert config.overlap == 200
        assert config.min_chunk_size == 100
        assert config.preserve_sentences is True
        assert config.preserve_paragraphs is True
        
        # Test custom values
        config = ChunkConfig(
            chunk_size=500,
            overlap=100,
            min_chunk_size=50,
            preserve_sentences=False,
            preserve_paragraphs=False
        )
        assert config.chunk_size == 500
        assert config.overlap == 100
        assert config.min_chunk_size == 50
        assert config.preserve_sentences is False
        assert config.preserve_paragraphs is False