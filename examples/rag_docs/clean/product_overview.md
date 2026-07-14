# RAGGuard Product Overview

## What RAGGuard Does

RAGGuard is a document question-answering assistant. Users upload documents, and
the assistant answers questions grounded in those documents using retrieval-augmented
generation. It supports PDFs, Markdown, and plain text.

## Retrieval

RAGGuard uses hybrid search: dense vector similarity combined with BM25 keyword
matching, fused with reciprocal rank fusion. The top candidates are reranked before
being passed to the language model. Every answer cites the specific chunks it used.

## Supported Languages

The assistant currently supports English documents. Support for additional
languages is on the roadmap for a future release.

## Availability

RAGGuard is available as a hosted service and as a self-managed Docker deployment.
The self-managed edition ships with the same retrieval pipeline as the hosted one.
