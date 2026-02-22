"""Tests for table extraction."""
import pytest
from app.services.table_extraction import extract_tables

SIMPLE_TABLE = """
<html><body>
<table>
    <thead>
        <tr><th>Name</th><th>Price</th><th>Stock</th></tr>
    </thead>
    <tbody>
        <tr><td>Widget A</td><td>$10</td><td>100</td></tr>
        <tr><td>Widget B</td><td>$20</td><td>50</td></tr>
        <tr><td>Widget C</td><td>$15</td><td>75</td></tr>
    </tbody>
</table>
</body></html>
"""

LAYOUT_TABLE = """
<html><body>
<table>
    <tr><td><img src="logo.png"/></td><td>Welcome to our site</td></tr>
    <tr><td colspan="2"><nav>Home | About | Contact</nav></td></tr>
</table>
</body></html>
"""

MULTI_TABLE = """
<html><body>
<table>
    <tr><th>Product</th><th>Rating</th></tr>
    <tr><td>A</td><td>4.5</td></tr>
    <tr><td>B</td><td>3.8</td></tr>
</table>
<table>
    <tr><th>Feature</th><th>Supported</th></tr>
    <tr><td>PDF</td><td>Yes</td></tr>
    <tr><td>CSV</td><td>Yes</td></tr>
</table>
</body></html>
"""


class TestTableExtraction:
    def test_simple_table(self):
        tables = extract_tables(SIMPLE_TABLE)
        assert len(tables) >= 1
        t = tables[0]
        assert "headers" in t
        assert "rows" in t
        assert t["headers"] == ["Name", "Price", "Stock"]
        assert len(t["rows"]) == 3

    def test_multiple_tables(self):
        tables = extract_tables(MULTI_TABLE)
        assert len(tables) == 2

    def test_no_tables(self):
        tables = extract_tables("<html><body><p>No tables here</p></body></html>")
        assert tables == []

    def test_table_has_data(self):
        tables = extract_tables(SIMPLE_TABLE)
        rows = tables[0]["rows"]
        assert rows[0] == ["Widget A", "$10", "100"]
        assert rows[1] == ["Widget B", "$20", "50"]
