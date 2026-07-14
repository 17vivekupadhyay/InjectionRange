# Security FAQ

## How is my data stored?

Uploaded documents and their embeddings are stored in your project's database.
Documents are never used to train shared models.

## Does RAGGuard follow instructions found inside documents?

No. In hardened mode, retrieved document content is treated strictly as data.
The assistant will not obey instructions embedded in documents, change its output
format because a document asked it to, or reveal system configuration.

## What is a canary value?

A canary is a fake, planted secret used to detect leakage. If a canary string ever
appears in a model response, it indicates the model was manipulated into disclosing
protected context. RAGGuard uses canaries purely for security testing.

## How do I report a vulnerability?

Email the security team through the address listed in your admin console.
