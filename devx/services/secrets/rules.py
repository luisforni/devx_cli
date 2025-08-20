PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret": r"(?i)aws(.{0,20})?(secret|access).{0,3}[:=]\s*[\"'][0-9a-zA-Z\/+=]{40}[\"']",
    "JWT": r"eyJ[a-zA-Z0-9_-]+?\.[a-zA-Z0-9._-]+?\.[a-zA-Z0-9._-]+",
    "Generic API Key": r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']",
    "Password in code": r"(?i)(password|passwd|pwd)\s*[:=]\s*[\"'][^\"']{6,}[\"']",
}
