# Configuration file for the Sphinx documentation builder.

# -- Project information -----------------------------------------------------

project = 'coffea-casa'
copyright = '2026, coffea-casa'
author = 'coffea-casa, UNL'
release = '0.1.0'

# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.ifconfig",
    "sphinx.ext.viewcode",
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'

html_title = "Coffea-Casa Documentation"

html_theme_options = {
    # Sidebar behaviour
    "navigation_depth": 4,
    "collapse_navigation": False,   # keep all sections expanded like Ceph
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    # Style
    "style_nav_header_background": "#1a1f2e",   # dark navy header (Ceph-like)
    "prev_next_buttons_location": "both",
    "style_external_links": True,
}

html_show_sphinx = True
html_show_sourcelink = True

html_static_path = ['_static']
html_css_files = ['custom.css']

html_logo = "_static/coffea-casa-logo.png"
