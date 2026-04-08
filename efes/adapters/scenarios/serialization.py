from __future__ import annotations

from efes.domain.models import PhaseData
from efes_core.adapters.scenarios.serialization import REGISTRY, from_json_dict, write_to_json, read_from_json

# extend the registry
REGISTRY.update({
    "PhaseData": PhaseData,
})

# simply expose functions from efes_core
from_json_dict = from_json_dict
write_to_json = write_to_json
read_from_json =read_from_json