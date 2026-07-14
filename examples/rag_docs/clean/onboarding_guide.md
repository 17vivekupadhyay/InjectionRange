# Onboarding Guide

## Step 1: Create an Account

Register with your email and a password. The first account created in a fresh
deployment is granted administrator rights.

## Step 2: Upload Documents

Use the document manager to upload your knowledge base. Structure-aware chunking
splits documents by headings, so well-structured Markdown yields better retrieval.

## Step 3: Ask Questions

Open a conversation and ask a question. The retrieval debug view shows which chunks
were retrieved, their scores, and whether the system is running in naive or
hardened mode.

## Step 4: Evaluate

Run the retrieval-quality eval harness against your golden query set to measure
recall@k and MRR after any change to chunking, embeddings, or the reranker.
