import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import requests


LOG_FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)


def load_rows(
    spreadsheet: Path,
    sku_column: str,
    title_column: str,
    color_column: Optional[str],
) -> List[Dict[str, str]]:
    if spreadsheet.suffix.lower() == ".csv":
        df = pd.read_csv(spreadsheet)
    else:
        df = pd.read_excel(spreadsheet)

    if df.empty:
        raise ValueError("Spreadsheet contains no rows")

    required_cols = [sku_column, title_column]
    if color_column:
        required_cols.append(color_column)

    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    rows: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        sku = str(row[sku_column]).strip()
        title = str(row[title_column]).strip()
        color = str(row[color_column]).strip() if color_column else ""
        rows.append({"sku": sku, "title": title, "color": color})

    return rows


def find_image(images_root: Path, sku: str, color: str) -> Path:
    sku_dir = images_root / sku
    if not sku_dir.exists() or not sku_dir.is_dir():
        raise FileNotFoundError(f"Missing folder for SKU {sku}: {sku_dir}")

    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    for file in sku_dir.iterdir():
        if file.is_file() and file.suffix.lower() in allowed_exts:
            if file.stem.lower() == color.lower():
                return file

    raise FileNotFoundError(f"No image for color '{color}' in {sku_dir}")


def set_nested_value(payload: Dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    current: Any = payload
    for key in keys[:-1]:
        if isinstance(current, list):
            key_index = int(key)
            current = current[key_index]
        else:
            current = current.setdefault(key, {})
    last_key = keys[-1]
    if isinstance(current, list):
        current[int(last_key)] = value
    else:
        current[last_key] = value


def get_nested_value(payload: Dict[str, Any], path: str) -> Any:
    keys = path.split(".")
    current: Any = payload
    for key in keys:
        if isinstance(current, list):
            current = current[int(key)]
        else:
            current = current[key]
    return current


def load_template(config: Dict[str, Any], session: requests.Session) -> Dict[str, Any]:
    if config.get("template_path"):
        template_path = Path(config["template_path"])
        return json.loads(template_path.read_text(encoding="utf-8"))

    template_endpoint = config.get("template_endpoint")
    if not template_endpoint:
        raise ValueError("Provide template_path or template_endpoint in config")

    response = session.request(
        config.get("template_method", "GET"),
        template_endpoint,
        json=config.get("template_payload"),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def build_session(config: Dict[str, Any]) -> requests.Session:
    session = requests.Session()
    if config.get("cookies"):
        session.headers.update({"Cookie": config["cookies"]})
    if config.get("headers"):
        session.headers.update(config["headers"])
    return session


def upload_image(
    session: requests.Session,
    config: Dict[str, Any],
    image_path: Path,
) -> str:
    endpoint = config.get("image_upload_endpoint")
    if not endpoint:
        raise ValueError("Missing image_upload_endpoint in config")

    field_name = config.get("image_upload_field", "file")
    data = config.get("image_upload_form", {})

    with image_path.open("rb") as f:
        files = {field_name: (image_path.name, f, "application/octet-stream")}
        response = session.request(
            config.get("image_upload_method", "POST"),
            endpoint,
            data=data,
            files=files,
            timeout=60,
        )
    response.raise_for_status()
    response_json = response.json()

    url_path = config.get("image_upload_response_path")
    if not url_path:
        raise ValueError("Missing image_upload_response_path in config")
    return get_nested_value(response_json, url_path)


def submit_product(
    session: requests.Session,
    config: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    endpoint = config.get("product_submit_endpoint")
    if not endpoint:
        raise ValueError("Missing product_submit_endpoint in config")

    response = session.request(
        config.get("product_submit_method", "POST"),
        endpoint,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def update_sku_paths(payload: Dict[str, Any], sku: str, paths: Iterable[str]) -> None:
    for path in paths:
        set_nested_value(payload, path, sku)


def update_color_images(
    payload: Dict[str, Any],
    color: str,
    image_url: str,
    config: Dict[str, Any],
) -> None:
    list_path = config.get("skc_list_path")
    if not list_path:
        return

    skc_list = get_nested_value(payload, list_path)
    if not isinstance(skc_list, list):
        raise ValueError(f"Expected list at {list_path}")

    parent_spec_name = config.get("skc_color_parent_name", "Color")
    image_path = config.get("skc_image_path", "carousel_gallery.0.url")
    color_image_path = config.get("skc_color_image_path", "color_image_url")

    for skc in skc_list:
        spec_list = skc.get("spec", [])
        match = any(
            spec.get("parent_spec_name") == parent_spec_name
            and spec.get("spec_name") == color
            for spec in spec_list
        )
        if match:
            set_nested_value(skc, image_path, image_url)
            if color_image_path:
                set_nested_value(skc, color_image_path, image_url)


def prepare_payload(
    template: Dict[str, Any],
    mapping: Dict[str, str],
    sku: str,
    title: str,
    color: str,
    image_url: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    payload = json.loads(json.dumps(template))
    set_nested_value(payload, mapping["sku"], sku)
    set_nested_value(payload, mapping["title"], title)
    set_nested_value(payload, mapping["image"], image_url)

    sku_paths = config.get("sku_paths", [])
    update_sku_paths(payload, sku, sku_paths)

    goods_image_path = config.get("goods_image_path")
    if goods_image_path:
        set_nested_value(payload, goods_image_path, image_url)

    update_color_images(payload, color, image_url, config)
    return payload


def process_rows(
    rows: Iterable[Dict[str, str]],
    images_root: Path,
    config: Dict[str, Any],
    dry_run: bool,
) -> List[Dict[str, Any]]:
    session = build_session(config)
    template = load_template(config, session)
    mapping = config.get("payload_paths", {})

    required_paths = {"sku", "title", "image"}
    if not required_paths.issubset(mapping):
        raise ValueError(f"payload_paths must include {sorted(required_paths)}")

    results = []

    for row in rows:
        sku = row["sku"]
        title = row["title"]
        color = row["color"]

        if not sku or not title or not color:
            results.append({
                "sku": sku,
                "status": "error",
                "message": "Missing sku/title/color",
            })
            continue

        try:
            image_path = find_image(images_root, sku, color)
        except FileNotFoundError as exc:
            results.append({"sku": sku, "status": "error", "message": str(exc)})
            continue

        if dry_run:
            results.append({"sku": sku, "status": "dry_run", "message": "Skipped upload"})
            continue

        try:
            image_url = upload_image(session, config, image_path)
            payload = prepare_payload(template, mapping, sku, title, color, image_url, config)
            response = submit_product(session, config, payload)
            results.append({
                "sku": sku,
                "status": "uploaded",
                "message": json.dumps(response)[:500],
            })
        except Exception as exc:  # noqa: BLE001
            results.append({"sku": sku, "status": "error", "message": str(exc)})

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload TEMU POD products by replacing the first image, SKU, and title.",
    )
    parser.add_argument("--spreadsheet", required=True, help="Excel or CSV file path")
    parser.add_argument("--sku-column", required=True, help="Column name for SKU")
    parser.add_argument("--title-column", required=True, help="Column name for Title")
    parser.add_argument("--color-column", required=True, help="Column name for Color")
    parser.add_argument("--images-root", required=True, help="Folder with SKU subfolders")
    parser.add_argument("--config", required=True, help="JSON config for TEMU endpoints")
    parser.add_argument("--dry-run", action="store_true", help="Validate without uploading")
    parser.add_argument("--report", default="temu_upload_report.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    rows = load_rows(
        Path(args.spreadsheet),
        sku_column=args.sku_column,
        title_column=args.title_column,
        color_column=args.color_column,
    )

    results = process_rows(
        rows,
        images_root=Path(args.images_root),
        config=config,
        dry_run=args.dry_run,
    )

    report_path = Path(args.report)
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    success_count = sum(1 for item in results if item["status"] == "uploaded")
    error_count = sum(1 for item in results if item["status"] == "error")
    logging.info("Completed. Uploaded: %s | Errors: %s", success_count, error_count)
    logging.info("Report written to %s", report_path)


if __name__ == "__main__":
    main()
