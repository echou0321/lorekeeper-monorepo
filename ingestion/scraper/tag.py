from config import ARC_SECTION_MAP, SPOILER_SENSITIVE_PATTERNS


def tag_section(section_title: str, intro_arc_index: int) -> int:
    normalized = section_title.lower().strip()
    return ARC_SECTION_MAP.get(normalized, intro_arc_index)


def is_spoiler_sensitive(section_title: str, content: str) -> bool:
    haystack = (section_title + ' ' + content).lower()
    return any(pattern in haystack for pattern in SPOILER_SENSITIVE_PATTERNS)
