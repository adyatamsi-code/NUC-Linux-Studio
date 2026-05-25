import pytest
from ui.utils import sanitize_color, get_closest_color, DEFAULT_COLOR


class TestUtils:
    def test_sanitize_color_valid_hex(self):
        """Test that a valid hex string is returned unchanged."""
        valid_hex = "#ffffff"
        assert sanitize_color(valid_hex) == valid_hex
        
        valid_hex2 = "#123456"
        assert sanitize_color(valid_hex2) == valid_hex2

    def test_sanitize_color_invalid_hex_length(self):
        """Test that invalid hex strings (wrong length) return default color."""
        assert sanitize_color("#fff") == DEFAULT_COLOR
        assert sanitize_color("#1234567") == DEFAULT_COLOR

    def test_sanitize_color_missing_hash(self):
        """Test that hex strings without a hash return default color."""
        assert sanitize_color("ffffff") == DEFAULT_COLOR

    def test_sanitize_color_invalid_type(self):
        """Test that None or non-string types return default color."""
        assert sanitize_color(None) == DEFAULT_COLOR
        assert sanitize_color(123456) == DEFAULT_COLOR

    def test_get_closest_color_exact_matches(self):
        """Test that get_closest_color returns expected names for exact RGB values."""
        assert get_closest_color(255, 0, 0) == "red"
        assert get_closest_color(0, 255, 0) == "green"
        assert get_closest_color(0, 0, 255) == "blue"
        assert get_closest_color(255, 255, 0) == "yellow"
        assert get_closest_color(0, 255, 255) == "teal"
        assert get_closest_color(128, 0, 128) == "purple"
        assert get_closest_color(255, 128, 0) == "orange"

    def test_get_closest_color_approximate_matches(self):
        """Test that get_closest_color returns the nearest color name for off-values."""
        # Almost red
        assert get_closest_color(250, 10, 10) == "red"
        # Almost blue
        assert get_closest_color(10, 10, 250) == "blue"
        # Grey should map to purple or teal depending on exact distance, 
        # but let's test a clear slight-orange
        assert get_closest_color(240, 130, 10) == "orange"
