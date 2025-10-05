-- Create a clean dimension view for symbols/metadata
CREATE OR REPLACE VIEW vw_symbols_dim AS
SELECT
  LOWER(TRIM(symbol))         AS symbol,
  name,
  sector,
  industry,
  exchange,
  is_active
FROM symbols_dim;
