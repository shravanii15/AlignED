select course_id, program_id
from {{ source('aligned', 'courses') }}
