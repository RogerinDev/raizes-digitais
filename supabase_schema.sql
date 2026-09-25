-- Ativa a extensão pgvector, essencial para a busca semântica
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabela global de Documentos para o RAG Institucional
CREATE TABLE IF NOT EXISTS documents (
    id bigserial PRIMARY KEY,
    content text,
    metadata jsonb,
    embedding vector(768)
);

-- Tabela de Histórico de Mensagens do LangChain (PostgresChatMessageHistory)
CREATE TABLE IF NOT EXISTS chat_memory (
    id serial PRIMARY KEY,
    session_id text NOT NULL,
    message jsonb NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Tabela auxiliar para mapeamento do UUID LangChain com o ID Numérico do Telegram
CREATE TABLE IF NOT EXISTS chat_mapping (
    uuid_session_id text PRIMARY KEY,
    telegram_chat_id bigint NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Procedure RPC para a Busca Híbrida usando Reciprocal Rank Fusion (RRF)
CREATE OR REPLACE FUNCTION match_documents(
    query_text text,
    query_embedding vector(768),
    match_count int DEFAULT 4
)
RETURNS TABLE (
    id int8,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
#variable_conflict use_column
DECLARE
    -- Constante k recomendada para o cálculo do Reciprocal Rank Fusion
    rrf_k int := 60;
BEGIN
    RETURN QUERY
    -- 1. Busca Baseada em Palavras-Chave (Full-Text Search nativo do Postgres)
    WITH fts_search AS (
        SELECT
            d.id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank(to_tsvector('portuguese', d.content), websearch_to_tsquery('portuguese', query_text)) DESC
            ) AS rank
        FROM documents d
        WHERE to_tsvector('portuguese', d.content) @@ websearch_to_tsquery('portuguese', query_text)
        LIMIT match_count * 2
    ),
    -- 2. Busca Vetorial por Similaridade Semântica (pgvector)
    vector_search AS (
        SELECT
            d.id,
            ROW_NUMBER() OVER (
                ORDER BY d.embedding <=> query_embedding
            ) AS rank
        FROM documents d
        ORDER BY d.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    -- 3. Combinação RRF (Reciprocal Rank Fusion)
    rrf_scored AS (
        SELECT
            COALESCE(fts.id, vec.id) AS doc_id,
            COALESCE(1.0 / (rrf_k + fts.rank), 0.0) +
            COALESCE(1.0 / (rrf_k + vec.rank), 0.0) AS rrf_score
        FROM fts_search fts
        -- O INNER JOIN força a interseção: o doc tem que ter a palavra exata e semântica correlata
        INNER JOIN vector_search vec ON fts.id = vec.id
    )
    -- 4. Retorno Final
    SELECT
        d.id,
        d.content,
        d.metadata,
        rrf.rrf_score::float AS similarity
    FROM rrf_scored rrf
    JOIN documents d ON d.id = rrf.doc_id
    ORDER BY rrf.rrf_score DESC
    LIMIT match_count;
END;
$$;
