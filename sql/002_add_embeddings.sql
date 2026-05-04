-- Add embedding_json columns for hybrid (dense + sparse) retrieval
ALTER TABLE ai_database_facts ADD COLUMN embedding_json TEXT NOT NULL DEFAULT '';
ALTER TABLE ai_code_facts ADD COLUMN embedding_json TEXT NOT NULL DEFAULT '';
