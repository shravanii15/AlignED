select cluster_id, role_label
from {{ source('aligned', 'role_clusters') }}
