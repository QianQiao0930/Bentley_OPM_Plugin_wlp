"""Build the C# add-in's runtime data from the sibling Python project.

This is a development-time export only. The deployed .NET add-in does not
start Python or import any Python module.
"""

import math
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
PYTHON_PROJECT = next(
    (candidate for candidate in (
        HERE.parent / "型钢截面生成器",  # deployed sibling C# project
        HERE.parent.parent,  # staging inside the Python project
    ) if (candidate / "steel_sections").is_dir()),
    None,
)
if PYTHON_PROJECT is None:
    raise RuntimeError("Cannot locate sibling Python steel_sections project")
sys.path.insert(0, str(PYTHON_PROJECT))

from steel_sections import steel_registry as registry  # noqa: E402


def write_string(stream, value):
    encoded = value.encode("utf-8")
    stream.write(struct.pack("<I", len(encoded)))
    stream.write(encoded)


def write_count(stream, value):
    stream.write(struct.pack("<I", value))


def export():
    target = HERE / "profiles.bin"
    total_profiles = 0
    total_segments = 0
    with target.open("wb") as stream:
        stream.write(b"SSP1")
        families = [registry.get_family(family_id) for family_id in registry.family_ids()]
        write_count(stream, len(families))
        for family in families:
            write_string(stream, family.identifier)
            write_string(stream, family.label)
            names = registry.profile_names(family.identifier)
            write_count(stream, len(names))
            builder = getattr(family.geometry, family.builder)
            for name in names:
                total_profiles += 1
                write_string(stream, name)
                section = registry.get_section(family.identifier, name)
                numeric = [(key, float(value)) for key, value in section.items()
                           if isinstance(value, (int, float))]
                write_count(stream, len(numeric))
                for key, value in numeric:
                    write_string(stream, key)
                    stream.write(struct.pack("<d", value))
                modes = registry.insertion_modes(family.identifier)
                write_count(stream, len(modes))
                for mode_id, mode_label in modes:
                    write_string(stream, mode_id)
                    write_string(stream, mode_label)
                    geometry = builder(section, mode_id, family.geometry.Point2d(0.0, 0.0))
                    assert geometry.is_closed_and_continuous(), (family.identifier, name, mode_id)
                    write_count(stream, len(geometry.segments))
                    for segment in geometry.segments:
                        total_segments += 1
                        is_arc = hasattr(segment, "center")
                        stream.write(struct.pack("<B", int(is_arc)))
                        if is_arc:
                            angle = segment.start_angle + segment.sweep / 2.0
                            mx = segment.center.x + segment.radius * math.cos(angle)
                            my = segment.center.y + segment.radius * math.sin(angle)
                        else:
                            mx = my = 0.0
                        stream.write(struct.pack("<6d", segment.start.x, segment.start.y,
                                                 mx, my, segment.end.x, segment.end.y))
    print(f"Exported {len(families)} families, {total_profiles} profiles, "
          f"{total_segments} segments: {target.stat().st_size} bytes")


if __name__ == "__main__":
    export()
