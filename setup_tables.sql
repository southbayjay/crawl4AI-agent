-- Drop existing table if it exists
DROP TABLE IF EXISTS public.websites;

-- Create the websites table
CREATE TABLE public.websites (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert the existing data
INSERT INTO public.websites (name, table_name) VALUES
('Unblu Documentation', 'unblu_docs'),
('PydanticAI Documentation', 'pydantic_ai_docs'),
('PythonUV Documentation', 'python_uv_docs'),
('Crawl4AI Documentation', 'crawl4ai_docs');

-- Enable RLS
ALTER TABLE public.websites ENABLE ROW LEVEL SECURITY;

-- Add RLS policy for read access
CREATE POLICY "Enable read access for all users" ON public.websites
    FOR SELECT
    USING (true);
