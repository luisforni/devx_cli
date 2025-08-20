import re
from devx.services.secrets.rules import PATTERNS

def _match_any(pattern, text):
    return re.search(pattern, text) is not None

def test_detects_jwt_token(tmp_path):
    sample = "header = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature'"
    assert _match_any(PATTERNS["JWT"], sample)

def test_detects_generic_api_key(tmp_path):
    sample = 'api_key = "A1234567890B1234"'
    assert _match_any(PATTERNS["Generic API Key"], sample)

def test_password_in_code(tmp_path):
    sample = "password = 'SuperSecret123'"
    assert _match_any(PATTERNS["Password in code"], sample)

def test_no_false_positive_on_normal_text():
    sample = "This is a normal file without tokens or secrets."
    assert not _match_any(PATTERNS["JWT"], sample)
    assert not _match_any(PATTERNS["Password in code"], sample)
