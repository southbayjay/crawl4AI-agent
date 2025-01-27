# Multi-Website RAG Implementation Plan

## Overview
This document outlines the plan to implement multi-website RAG support in the crawl4AI agent. The system will allow storing and querying RAG data from multiple websites independently.

## Components

### 1. Database Schema

#### Websites Table
```sql
create table websites (
    id bigserial primary key,
    name varchar not null unique,
    table_name varchar not null unique,
    created_at timestamp with time zone default timezone('utc'::text, now()) not null
);
```

#### Dynamic Website Tables
Each website will have its own table following the site_pages structure:
- Vector-enabled (pgvector)
- Full text content storage
- Metadata support
- Vector similarity search function

### 2. Dynamic Table Creation
A PostgreSQL function will handle creating new website tables:
```sql
create or replace function create_website_table(table_name text)
```
This function will:
- Create a new table with the given name
- Set up necessary indexes
- Create a matching vector search function

### 3. UI Updates (streamlit_ui.py)

#### New Features
- Website selector dropdown in sidebar
- Dynamic table selection for RAG queries
- Error handling for no websites

#### Key Functions
```python
def get_available_websites():
    """Fetch available websites from the database."""
    
async def process_query(query: str):
    """Process RAG query using selected website table."""
```

## Implementation Steps

1. **Database Setup**
   - Create websites table
   - Implement create_website_table function
   - Test table creation

2. **UI Updates**
   - Add website selector to sidebar
   - Modify RAG query logic
   - Add error handling

3. **Testing**
   - Test website table creation
   - Verify RAG queries work per website
   - Validate UI functionality

## Usage

1. **Adding a New Website**
   ```sql
   -- 1. Add website to websites table
   INSERT INTO websites (name, table_name) VALUES ('example.com', 'example_com');
   
   -- 2. Create website table
   SELECT create_website_table('example_com');
   ```

2. **Querying Website Data**
   - Select website from dropdown
   - Enter query as normal
   - Results will come from selected website's table

## Notes
- Table names should be sanitized versions of website names
- Each website table maintains its own vector search capabilities
- UI automatically loads available websites on startup
