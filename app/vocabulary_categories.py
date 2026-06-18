from __future__ import annotations

# Communication categories defined for Sara as generic hotspot metadata.
# They are not a diagnostic instrument and do not reproduce any clinical,
# commercial, or protected vocabulary assessment taxonomy.
# The UI displays the categories in three columns for usability. Stored labels
# are canonical English labels so project JSON and research logs remain stable
# across UI languages.

COMMUNICATION_CATEGORY_GROUP = "sara_communication"

COMMUNICATION_CATEGORIES = [
    {"id": "none", "label": "None", "group": None},
    {"id": "person", "label": "Person / proper name", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "noun", "label": "Noun / object", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "verb", "label": "Verb / action", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "descriptor", "label": "Descriptor", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "social_expression", "label": "Social expression", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "function_word", "label": "Function word", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "place", "label": "Place", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "category", "label": "Category / folder", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "priority", "label": "Priority / emergency", "group": COMMUNICATION_CATEGORY_GROUP},
    {"id": "other", "label": "Other", "group": COMMUNICATION_CATEGORY_GROUP},
]

# Backward-compatible public name used by existing code/tests. The category
# system is now Sara's own generic communication-category set.
VOCABULARY_CATEGORIES = COMMUNICATION_CATEGORIES

_CATEGORY_BY_ID = {category["id"]: category for category in COMMUNICATION_CATEGORIES}


def get_vocabulary_category(category_id: str | None):
    category_id = "none" if category_id in {None, "", "null"} else str(category_id)
    return _CATEGORY_BY_ID.get(category_id, _CATEGORY_BY_ID["none"])


def get_categories_by_group(group: str | None):
    return [category for category in COMMUNICATION_CATEGORIES if category.get("group") == group]


def vocabulary_translation_key(category_id: str | None) -> str:
    category = get_vocabulary_category(category_id)
    return f"vocabulary_category_{category['id']}"


COMMUNICATION_CATEGORY_UI_COLUMNS = [
    ["none", "person", "noun", "verb"],
    ["descriptor", "social_expression", "function_word", "place"],
    ["category", "priority", "other"],
]

# Backward-compatible name for the three-column UI layout.
VOCABULARY_CATEGORY_UI_COLUMNS = COMMUNICATION_CATEGORY_UI_COLUMNS


def get_vocabulary_category_columns():
    return [[get_vocabulary_category(category_id) for category_id in column] for column in COMMUNICATION_CATEGORY_UI_COLUMNS]
