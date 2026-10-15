from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Optional

try:
    from .installer import archive as _archive
    from .installer import install as _install
    from .installer import report as _report
    from .installer import source as _source
    from .installer import thin_state as _thin_state
except ImportError:  # pragma: no cover - direct CLI execution fallback
    from installer import archive as _archive  # type: ignore
    from installer import install as _install  # type: ignore
    from installer import report as _report  # type: ignore
    from installer import source as _source  # type: ignore
    from installer import thin_state as _thin_state  # type: ignore


def _main(argv: Optional[list[str]] = None) -> int:
    # This entry point resolves sources and orchestrates layers; dedicated modules own archives, transactions, reports, downloads, and Thin state.
    parser = argparse.ArgumentParser(description="User Skill package installer")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--order-id", dest="order_id")
    source.add_argument("--file")
    source.add_argument("--check-deps", dest="check_deps")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--install-root", default="")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing Skill directory after user confirmation",
    )
    args = parser.parse_args(argv)

    try:
        if args.check_deps:
            target = Path(args.check_deps)
            if not target.exists() or not target.is_dir():
                print(f"invalid package directory: {target}", file=sys.stderr)
                return 1
            container, roots = _archive.discover_package_layout(target)
            shared = (
                tuple(path for path in sorted(container.iterdir()) if path not in roots)
                if container not in roots
                else ()
            )
            installed = _install.InstalledPackage(roots, shared)
            print(json.dumps(_report.build_install_report(
                installed,
                execute_installers=False,
            )))
            return 0

        metadata = {}
        if args.file:
            archive_path = Path(args.file)
        else:
            archive_path, metadata = _source.download_package(
                args.order_id,
                base_url=args.base_url,
            )
        try:
            order_detail = (
                _source._fetch_order_detail(
                    args.order_id,
                    base_url=_source._resolve_base_url(args.base_url),
                )
                if args.order_id
                else {}
            )
            destination_root = (
                Path(args.install_root).expanduser() if args.install_root else None
            )
            installed = _install.install_from_file(
                archive_path,
                destination_root=destination_root,
                preferred_dir_name=metadata.get("folder_name"),
                fallback_dir_names=(
                    order_detail.get("agent_id"),
                    metadata.get("thin_skill_template_id"),
                ),
                overwrite=args.overwrite,
                package_type=metadata.get("type") or "download",
            )
        finally:
            if args.order_id:
                shutil.rmtree(archive_path.parent, ignore_errors=True)

        report = _report.build_install_report(installed)
        if metadata.get("type"):
            report["package_type"] = metadata["type"]
        if metadata.get("thin_skill_template_id"):
            report["thin_skill_template_id"] = metadata["thin_skill_template_id"]
        if metadata.get("license_id") is not None:
            report["license_id"] = metadata["license_id"]
        if metadata.get("type") == "thin_skill":
            report["state_sync"] = _thin_state.sync_thin_skill_state_after_install(
                args.order_id,
                metadata,
                installed.skill_dirs[0],
                base_url=args.base_url,
            )

        print(json.dumps(report))
        return 0
    except (RuntimeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_main())
