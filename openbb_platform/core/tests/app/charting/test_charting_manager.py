"""Tests for ``ChartingManager`` engine resolution.

Every assertion goes through the real ``ExtensionLoader`` / ``importlib.metadata``
discovery path and a real ``SystemService``. The fixture engine package is
installed once for this test package (see ``conftest.py``); nothing is mocked.
"""

from openbb_core.app.charting import ChartingManager


class TestChartingManager:
    """Resolve the active charting engine, with and without overrides."""

    def test_default_resolves_real_charting_engine(self):
        """With no override, the installed ``charting`` accessor is resolved."""
        ext = ChartingManager.get_extension()
        assert ext is not None
        assert ext.name == "charting"
        assert ChartingManager.is_installed() is True
        assert ChartingManager.accessor_name() == "charting"
        assert ChartingManager.has_chart("/equity/price/historical") is True

    def test_override_by_entry_point_name(self, charting_config):
        """``charting_extension`` may name the alternate engine's entry point."""
        charting_config(charting_extension="fake_engine")

        ext = ChartingManager.get_extension()
        assert ext is not None
        assert ext.name == "fake_charting"
        assert ChartingManager.accessor_name() == "fake_charting"

        engine = ChartingManager.get_charting_class()
        assert engine.__name__ == "FakeCharting"
        assert ChartingManager.functions() == ["fake_alt_chart"]
        assert ChartingManager.has_chart("/fake/alt/chart") is True

    def test_override_by_accessor_name(self, charting_config):
        """``charting_extension`` may name the alternate engine's accessor."""
        charting_config(charting_extension="fake_charting")

        engine = ChartingManager.get_charting_class()
        assert engine.__name__ == "FakeCharting"

    def test_unknown_override_resolves_to_none(self, charting_config):
        """An override that matches nothing yields no engine."""
        charting_config(charting_extension="does_not_exist")

        assert ChartingManager.get_extension() is None
        assert ChartingManager.is_installed() is False
        assert ChartingManager.get_charting_class() is None
        assert ChartingManager.functions() == []
        assert ChartingManager.has_chart("/equity/price/historical") is False

    def test_engine_functions_error_is_swallowed(self, charting_config):
        """A failing engine ``functions()`` resolves to an empty list, not a crash."""
        charting_config(charting_extension="fake_boom_charting")

        engine = ChartingManager.get_charting_class()
        assert engine.__name__ == "FakeBoomCharting"
        assert ChartingManager.functions() == []
        assert ChartingManager.has_chart("/anything") is False
