select skill_id, canonical_name as skill_name, taxonomy_source, category
from {{ source('aligned', 'skills') }}
