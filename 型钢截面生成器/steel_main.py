"""OpenPlant / MicroStation entry point for the unified steel-section tool."""

from __future__ import division

import importlib
import os

from MSPyBentley import WString
from MSPyMstnPlatform import PythonKeyinManager

import steel_channel_data
import steel_channel_geometry
import steel_equal_angle_data
import steel_equal_angle_geometry
import steel_hbeam_data
import steel_hbeam_geometry
import steel_hk_data
import steel_ibeam_data
import steel_ibeam_geometry
import steel_tapered_channel_data
import steel_tapered_channel_geometry
import steel_unequal_angle_data
import steel_unequal_angle_geometry
import steel_registry
import steel_sweep_geometry
import steel_tool
import steel_ui


_COMMANDS_LOADED = False


def _reload_runtime_modules():
    """Reload only this plug-in's uniquely named modules."""
    importlib.invalidate_caches()
    for module in (
            steel_channel_data, steel_channel_geometry,
            steel_ibeam_data, steel_ibeam_geometry,
            steel_tapered_channel_data, steel_tapered_channel_geometry,
            steel_equal_angle_data, steel_equal_angle_geometry,
            steel_unequal_angle_data, steel_unequal_angle_geometry,
            steel_hbeam_data, steel_hbeam_geometry, steel_hk_data,
            steel_registry, steel_sweep_geometry, steel_tool, steel_ui):
        importlib.reload(module)


def OpenSteelSectionGenerator():
    _reload_runtime_modules()
    steel_ui.show_steel_dialog()


def PlaceDefaultSteelSection():
    _reload_runtime_modules()
    family_id = "parallel_channel"
    steel_tool.start_placement(
        family_id,
        steel_registry.default_profile(family_id),
        steel_registry.default_insertion_mode(family_id),
    )


def RegisterKeyins():
    global _COMMANDS_LOADED
    if _COMMANDS_LOADED:
        return
    command_xml = os.path.join(os.path.dirname(__file__), "SteelSectionGenerator.commands.xml")
    PythonKeyinManager.GetManager().LoadCommandTableFromXml(
        WString(__file__), WString(command_xml)
    )
    _COMMANDS_LOADED = True


def PyMain():
    RegisterKeyins()
    OpenSteelSectionGenerator()


if __name__ == "__main__":
    PyMain()
