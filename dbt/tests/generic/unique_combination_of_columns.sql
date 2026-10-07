{% test unique_combination_of_columns(model, combination) %}
-- Fails for every combination of the given columns that appears more than once (nulls count as equal).
select {{ combination | join(', ') }}, count(*) as n
from {{ model }}
group by {{ combination | join(', ') }}
having count(*) > 1
{% endtest %}
