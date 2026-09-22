import sys
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s159_documented_pss_schema as schema


class DocumentedPssSchemaTests(unittest.TestCase):
    def test_documented_fields_are_noncausal_and_identity_unknown(self):
        result = schema.validate_entry({
            "handle": 17,
            "type": "Event",
            "object_type": 4,
            "type_name": "Event",
            "name_state": "UNAVAILABLE",
            "attributes": {"manual_reset": True},
            "type_specific_information": {"signaled": False},
            "capture_time_filetime": 123,
            "object_identity": "UNKNOWN",
        })
        self.assertTrue(result["valid"])
        self.assertFalse(result["causal_timing_eligible"])

    def test_reserved_fields_are_rejected(self):
        with self.assertRaisesRegex(schema.SchemaError, "S159_RESERVED_PSS_FIELD"):
            schema.validate_entry({"type": "Event", "creation_time_filetime": 123})

    def test_identity_claim_is_rejected(self):
        with self.assertRaisesRegex(schema.SchemaError, "S159_OBJECT_IDENTITY_UNPROVEN"):
            schema.validate_entry({"type": "Event", "object_identity": "same-object"})


if __name__ == "__main__":
    unittest.main()
