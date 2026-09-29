"""Command-line project and export tools."""

from __future__ import annotations

import argparse
from pathlib import Path

from blipkit import __version__
from blipkit.core.export import export_project
from blipkit.core.project import BlipkitProject


def create_project(args: argparse.Namespace) -> int:
    path = Path(args.path)
    project = BlipkitProject.create(path, args.name or path.stem, args.template)
    try:
        print(f"Created {project.path}")
    finally:
        project.close()
    return 0


def list_assets(args: argparse.Namespace) -> int:
    project = BlipkitProject.open(Path(args.project))
    try:
        assets = project.assets()
        if not assets:
            print("No assets.")
            return 0
        for asset in assets:
            print(f"{asset.kind:<7} {asset.name[:24]:<24} {asset.duration:6.2f}s  {asset.path}")
        return 0
    finally:
        project.close()


def export_assets(args: argparse.Namespace) -> int:
    project = BlipkitProject.open(Path(args.project))
    try:
        result = export_project(
            project,
            destination=Path(args.output),
            engine=args.engine,
            audio_format=args.format,
            progress=lambda current, total, name: print(f"[{current}/{total}] {name}"),
        )
        for path in result.files:
            print(f"  -> {path}")
        for failure in result.failed:
            print(f"  !! {failure}")
        return 1 if result.failed else 0
    finally:
        project.close()


def project_info(args: argparse.Namespace) -> int:
    project = BlipkitProject.open(Path(args.project))
    try:
        meta = project.metadata
        print(f"Project : {meta.name}")
        print(f"Path    : {project.path}")
        print(f"Template: {meta.template}")
        print(f"Engine  : {meta.engine}")
        print(
            f"Audio   : {meta.sample_rate} Hz / {meta.bit_depth}-bit / "
            f"{meta.channels} / .{meta.export_format}"
        )
        print(f"Assets  : {len(project.assets())}")
        return 0
    finally:
        project.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blipkit",
        description="Blipkit game-audio toolkit",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    create = sub.add_parser("create", help="create a .bkproj project")
    create.add_argument("path")
    create.add_argument("--name", default="")
    create.add_argument(
        "--template",
        choices=["Blank", "RPG", "Platformer", "Horror", "Puzzle", "Action"],
        default="RPG",
    )
    create.set_defaults(func=create_project)

    listing = sub.add_parser("list", help="list project assets")
    listing.add_argument("project")
    listing.set_defaults(func=list_assets)

    export = sub.add_parser("export", help="render and export project assets")
    export.add_argument("project")
    export.add_argument("output")
    export.add_argument(
        "--engine",
        choices=["None", "Unity", "Godot 4", "Unreal Engine 5", "Web", "Custom"],
        default="None",
    )
    export.add_argument(
        "--format",
        choices=["wav", "ogg", "mp3", "flac"],
        default=None,
    )
    export.set_defaults(func=export_assets)

    info = sub.add_parser("info", help="show project metadata")
    info.add_argument("project")
    info.set_defaults(func=project_info)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
