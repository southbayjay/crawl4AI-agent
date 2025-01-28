-- Enable the pgvector extension if not already enabled
create extension if not exists vector;

-- Create the websites table to track all RAG-enabled websites
create table if not exists websites (
    id bigserial primary key,
    name varchar not null unique,
    table_name varchar not null unique,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Function to create a new website table with vector search capabilities
create or replace function create_website_table(table_name text)
returns void
language plpgsql
as $$
begin
    -- Create the table
    execute format('
        create table if not exists %I (
            id bigserial primary key,
            url varchar not null,
            chunk_number integer not null,
            title varchar not null,
            summary varchar not null,
            content text not null,
            metadata jsonb not null default ''{}'',
            embedding vector(1536),
            created_at timestamp with time zone default timezone(''utc''::text, now()) not null,
            unique(url, chunk_number)
        )', table_name);
        
    -- Create indexes
    execute format('create index if not exists %I_embedding_idx on %I using ivfflat (embedding vector_cosine_ops)', table_name, table_name);
    execute format('create index if not exists %I_metadata_idx on %I using gin (metadata)', table_name, table_name);
    
    -- Create the vector search function
    execute format('
        create or replace function match_%I (
            query_embedding vector(1536),
            match_count int default 10,
            filter jsonb DEFAULT ''{}'',
            similarity_threshold float default 0.5
        ) returns table (
            id bigint,
            url varchar,
            chunk_number integer,
            title varchar,
            summary varchar,
            content text,
            metadata jsonb,
            similarity float
        )
        language plpgsql
        as $func$
        begin
            return query
            select
                id,
                url,
                chunk_number,
                title,
                summary,
                content,
                metadata,
                1 - (embedding <=> query_embedding) as similarity
            from %I
            where metadata @> filter
            and 1 - (embedding <=> query_embedding) > similarity_threshold
            order by similarity desc
            limit match_count;
        end;
        $func$;
    ', table_name, table_name);
end;
$$;

-- Create tables for each website
SELECT create_website_table('unblu_docs');
SELECT create_website_table('pydantic_ai_docs');
SELECT create_website_table('python_uv_docs');
SELECT create_website_table('crawl4ai_docs');

-- Insert website information
INSERT INTO websites (name, table_name) VALUES
    ('Unblu Documentation', 'unblu_docs'),
    ('PydanticAI Documentation', 'pydantic_ai_docs'),
    ('PythonUV Documentation', 'python_uv_docs'),
    ('Crawl4AI Documentation', 'crawl4ai_docs')
ON CONFLICT (name) DO NOTHING;
