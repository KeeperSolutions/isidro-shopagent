CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    rating DOUBLE PRECISION NOT NULL,
    embedding VECTOR(1536) NOT NULL
);

CREATE TABLE IF NOT EXISTS variants (
    sku TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products (id) ON DELETE CASCADE,
    size TEXT NOT NULL,
    color TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    inventory INT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products (category);
CREATE INDEX IF NOT EXISTS idx_variants_product_id ON variants (product_id);
CREATE INDEX IF NOT EXISTS idx_variants_price ON variants (price);
