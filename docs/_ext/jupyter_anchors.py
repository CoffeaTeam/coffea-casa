"""Heading anchors matching Jupyter's, for the rendered gallery notebooks."""


def heading_slug(text):
    """Jupyter's anchor for a heading: its text with spaces as dashes."""
    return text.strip().replace(" ", "-")
