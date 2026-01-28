diff --git a/app.py b/app.py
index 554e1f4f2fb8bc68c76dd6fcca31dd375664c5cc..c0b61d19ce00f49a925bb142a09bbfe38fc1b1c6 100644
--- a/app.py
+++ b/app.py
@@ -1,153 +1,323 @@
-import streamlit as st
-from PIL import Image, ImageOps, ImageEnhance
-import io
-import base64
-import numpy as np
-import openai
-import hashlib
-import tempfile
-import os
-from supabase import create_client, Client
-
-st.set_page_config(page_title="AI Shirt Tool 1-100", layout="wide")
-st.title("🛠️ AI Shirt Tools 901-1000")
-
-# Mode selection
-app_mode = st.sidebar.selectbox("Select Application", [
-    "👕 T-Shirt Title Generator"
-])
-
-# Supabase config
-SUPABASE_URL = "https://hryhwjkwpgzwxxhpnjwa.supabase.co"
-SUPABASE_KEY = st.secrets.get("supabase_key")
-BUCKET_NAME = "images"
-supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
-
-# OpenAI API key
-api_key = st.secrets.get("openai_api_key")
-
-if app_mode == "👕 T-Shirt Title Generator":
-    st.header("👕 AI Shirt Name Generator")
-
-    if not api_key:
-        st.warning("👈 Please set your OpenAI API key in Streamlit Secrets as `openai_api_key`.")
+import argparse
+import json
+import logging
+from pathlib import Path
+from typing import Any, Dict, Iterable, List, Optional
+
+import pandas as pd
+import requests
+
+
+LOG_FORMAT = "%(levelname)s: %(message)s"
+logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
+
+
+def load_rows(
+    spreadsheet: Path,
+    sku_column: str,
+    title_column: str,
+    color_column: Optional[str],
+) -> List[Dict[str, str]]:
+    if spreadsheet.suffix.lower() == ".csv":
+        df = pd.read_csv(spreadsheet)
     else:
-        openai.api_key = api_key
-
-        # Expanded color options
-        shirt_color = st.selectbox("👕 Shirt Color:", [
-            "Black", "White", "Grey", "Red", 
-            "Blue", "Green", "Yellow", "Pink", "Purple", 
-            "Orange", "Brown", "Beige", "Navy", "Teal"
-        ])
-
-        # Expanded clothing type options
-        shirt_type = st.selectbox("👗 Clothing Type:", [
-            "T-Shirt", "Crop Top", "Tank Top", 
-            "Hoodie", "Sweatshirt", "Long Sleeve", "Polo Shirt"
-        ])
-
-        shirt_gender = st.radio("🫍 Gender:", ["Men", "Women"], horizontal=True)
-        descriptor_word = st.text_input("✨ Custom Word for Shirt Title (e.g., 'Pure', 'Luck', 'Urban')", value="Pure")
-        custom_keyword = st.text_input("🔑 Custom Keyword at the End (optional)", value="")
-
-        # Preview of example title
-        example_preview = f"{shirt_gender}'s {descriptor_word} - {shirt_color} {shirt_type}: \"AI-Generated Design\" - {custom_keyword if custom_keyword else ''}"
-        st.markdown(f"**Preview Example:** _{example_preview}_")
-
-        uploaded_files = st.file_uploader("Upload T-shirt design images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
-
-        if uploaded_files:  # Check if files are uploaded
-            def preprocess_image(image: Image.Image, color: str) -> Image.Image:
-                gray = ImageOps.grayscale(image)
-                np_img = np.array(gray)
-                # List of dark colors where enhancement is needed
-                dark_colors = ["Black", "Navy", "Brown", "Purple"]
-                
-                if color in dark_colors:
-                    contrast = ImageEnhance.Contrast(gray).enhance(2.5)
-                    inverted = ImageOps.invert(contrast)
-                    return inverted.convert("RGB")
-                else:
-                    white_ratio = (np_img > 220).sum() / np_img.size
-                    if white_ratio > 0.75:
-                        contrast = ImageEnhance.Contrast(gray).enhance(2.5)
-                        inverted = ImageOps.invert(contrast)
-                        return inverted.convert("RGB")
-                return image
-
-            def encode_image(image: Image.Image, color: str) -> str:
-                image = preprocess_image(image, color)
-                buffered = io.BytesIO()
-                image.save(buffered, format="PNG")
-                return base64.b64encode(buffered.getvalue()).decode()
-
-            def generate_title_with_gpt(image_b64: str, gender: str, color: str, type: str) -> str:
-                def call_gpt(prompt_text):
-                    messages = [
-                        {
-                            "role": "system",
-                            "content": "You're a creative product copywriter for a fashion brand. Write short, stylish, eye-catching T-shirt product titles from image designs."
-                        },
-                        {
-                            "role": "user",
-                            "content": [
-                                {"type": "text", "text": prompt_text},
-                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
-                            ]
-                        }
-                    ]
-                    response = openai.chat.completions.create(
-                        model="gpt-4o",
-                        messages=messages,
-                        max_tokens=100
-                    )
-                    return response.choices[0].message.content.strip()
-
-                prompt = f"Generate a detailed and stylish product title for a {color.lower()} {type} for {gender.lower()}s. Base the title on the printed artwork in the image."
-                result = call_gpt(prompt)
-
-                if "can't help" in result.lower() or "i'm sorry" in result.lower():
-                    fallback_prompt = f"Write a trendy product title for the {type} shown in the image."
-                    result = call_gpt(fallback_prompt)
-
-                return result
-
-            def sanitize_title(title: str) -> str:
-                # Replace accented Spanish letters manually
-                replacements = {
-                    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
-                    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
-                    'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U'
-                }
-
-                # Replace accented letters
-                for accented_char, plain_char in replacements.items():
-                    title = title.replace(accented_char, plain_char)
-
-                # Remove all symbols except '-' and ':'
-                sanitized = ''.join(char if char.isalnum() or char in ['-', ':', ' '] else '' for char in title)
-
-                return sanitized
-
-            results = []
-            with st.spinner("🧐 Generating creative product titles with GPT-4 Vision..."):
-                for file in uploaded_files:
-                    img = Image.open(file).convert("RGB")
-                    try:
-                        img_b64 = encode_image(img, shirt_color)  # Pass shirt_color here
-                        title = generate_title_with_gpt(img_b64, shirt_gender, shirt_color, shirt_type)
-                        full_title = f"{shirt_gender}'s {descriptor_word} - {shirt_color} {shirt_type}: \"{title}\""
-                        if custom_keyword:
-                            full_title += f" - {custom_keyword}"
-
-                        sanitized_title = sanitize_title(full_title)
-                        results.append(sanitized_title)
-                    except Exception as e:
-                        results.append(f"ERROR: {e}")
-
-            st.success("✅ All titles generated!")
-            st.text_area("📝 Generated T-Shirt Titles", "\n".join(results), height=300)
+        df = pd.read_excel(spreadsheet)
+
+    if df.empty:
+        raise ValueError("Spreadsheet contains no rows")
+
+    required_cols = [sku_column, title_column]
+    if color_column:
+        required_cols.append(color_column)
+
+    for col in required_cols:
+        if col not in df.columns:
+            raise ValueError(f"Missing column: {col}")
+
+    rows: List[Dict[str, str]] = []
+    for _, row in df.iterrows():
+        sku = str(row[sku_column]).strip()
+        title = str(row[title_column]).strip()
+        color = str(row[color_column]).strip() if color_column else ""
+        rows.append({"sku": sku, "title": title, "color": color})
 
+    return rows
+
+
+def find_image(images_root: Path, sku: str, color: str) -> Path:
+    sku_dir = images_root / sku
+    if not sku_dir.exists() or not sku_dir.is_dir():
+        raise FileNotFoundError(f"Missing folder for SKU {sku}: {sku_dir}")
+
+    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
+    for file in sku_dir.iterdir():
+        if file.is_file() and file.suffix.lower() in allowed_exts:
+            if file.stem.lower() == color.lower():
+                return file
+
+    raise FileNotFoundError(f"No image for color '{color}' in {sku_dir}")
+
+
+def set_nested_value(payload: Dict[str, Any], path: str, value: Any) -> None:
+    keys = path.split(".")
+    current: Any = payload
+    for key in keys[:-1]:
+        if isinstance(current, list):
+            key_index = int(key)
+            current = current[key_index]
         else:
-            st.warning("Please upload at least one image to generate titles.")
+            current = current.setdefault(key, {})
+    last_key = keys[-1]
+    if isinstance(current, list):
+        current[int(last_key)] = value
+    else:
+        current[last_key] = value
+
+
+def get_nested_value(payload: Dict[str, Any], path: str) -> Any:
+    keys = path.split(".")
+    current: Any = payload
+    for key in keys:
+        if isinstance(current, list):
+            current = current[int(key)]
+        else:
+            current = current[key]
+    return current
+
+
+def load_template(config: Dict[str, Any], session: requests.Session) -> Dict[str, Any]:
+    if config.get("template_path"):
+        template_path = Path(config["template_path"])
+        return json.loads(template_path.read_text(encoding="utf-8"))
+
+    template_endpoint = config.get("template_endpoint")
+    if not template_endpoint:
+        raise ValueError("Provide template_path or template_endpoint in config")
+
+    response = session.request(
+        config.get("template_method", "GET"),
+        template_endpoint,
+        json=config.get("template_payload"),
+        timeout=30,
+    )
+    response.raise_for_status()
+    return response.json()
+
+
+def build_session(config: Dict[str, Any]) -> requests.Session:
+    session = requests.Session()
+    if config.get("cookies"):
+        session.headers.update({"Cookie": config["cookies"]})
+    if config.get("headers"):
+        session.headers.update(config["headers"])
+    return session
+
+
+def upload_image(
+    session: requests.Session,
+    config: Dict[str, Any],
+    image_path: Path,
+) -> str:
+    endpoint = config.get("image_upload_endpoint")
+    if not endpoint:
+        raise ValueError("Missing image_upload_endpoint in config")
+
+    field_name = config.get("image_upload_field", "file")
+    data = config.get("image_upload_form", {})
+
+    with image_path.open("rb") as f:
+        files = {field_name: (image_path.name, f, "application/octet-stream")}
+        response = session.request(
+            config.get("image_upload_method", "POST"),
+            endpoint,
+            data=data,
+            files=files,
+            timeout=60,
+        )
+    response.raise_for_status()
+    response_json = response.json()
+
+    url_path = config.get("image_upload_response_path")
+    if not url_path:
+        raise ValueError("Missing image_upload_response_path in config")
+    return get_nested_value(response_json, url_path)
+
+
+def submit_product(
+    session: requests.Session,
+    config: Dict[str, Any],
+    payload: Dict[str, Any],
+) -> Dict[str, Any]:
+    endpoint = config.get("product_submit_endpoint")
+    if not endpoint:
+        raise ValueError("Missing product_submit_endpoint in config")
+
+    response = session.request(
+        config.get("product_submit_method", "POST"),
+        endpoint,
+        json=payload,
+        timeout=60,
+    )
+    response.raise_for_status()
+    return response.json()
+
+
+def update_sku_paths(payload: Dict[str, Any], sku: str, paths: Iterable[str]) -> None:
+    for path in paths:
+        set_nested_value(payload, path, sku)
+
+
+def update_color_images(
+    payload: Dict[str, Any],
+    color: str,
+    image_url: str,
+    config: Dict[str, Any],
+) -> None:
+    list_path = config.get("skc_list_path")
+    if not list_path:
+        return
+
+    skc_list = get_nested_value(payload, list_path)
+    if not isinstance(skc_list, list):
+        raise ValueError(f"Expected list at {list_path}")
+
+    parent_spec_name = config.get("skc_color_parent_name", "Color")
+    image_path = config.get("skc_image_path", "carousel_gallery.0.url")
+    color_image_path = config.get("skc_color_image_path", "color_image_url")
+
+    for skc in skc_list:
+        spec_list = skc.get("spec", [])
+        match = any(
+            spec.get("parent_spec_name") == parent_spec_name
+            and spec.get("spec_name") == color
+            for spec in spec_list
+        )
+        if match:
+            set_nested_value(skc, image_path, image_url)
+            if color_image_path:
+                set_nested_value(skc, color_image_path, image_url)
+
+
+def prepare_payload(
+    template: Dict[str, Any],
+    mapping: Dict[str, str],
+    sku: str,
+    title: str,
+    color: str,
+    image_url: str,
+    config: Dict[str, Any],
+) -> Dict[str, Any]:
+    payload = json.loads(json.dumps(template))
+    set_nested_value(payload, mapping["sku"], sku)
+    set_nested_value(payload, mapping["title"], title)
+    set_nested_value(payload, mapping["image"], image_url)
+
+    sku_paths = config.get("sku_paths", [])
+    update_sku_paths(payload, sku, sku_paths)
+
+    goods_image_path = config.get("goods_image_path")
+    if goods_image_path:
+        set_nested_value(payload, goods_image_path, image_url)
+
+    update_color_images(payload, color, image_url, config)
+    return payload
+
+
+def process_rows(
+    rows: Iterable[Dict[str, str]],
+    images_root: Path,
+    config: Dict[str, Any],
+    dry_run: bool,
+) -> List[Dict[str, Any]]:
+    session = build_session(config)
+    template = load_template(config, session)
+    mapping = config.get("payload_paths", {})
+
+    required_paths = {"sku", "title", "image"}
+    if not required_paths.issubset(mapping):
+        raise ValueError(f"payload_paths must include {sorted(required_paths)}")
+
+    results = []
+
+    for row in rows:
+        sku = row["sku"]
+        title = row["title"]
+        color = row["color"]
+
+        if not sku or not title or not color:
+            results.append({
+                "sku": sku,
+                "status": "error",
+                "message": "Missing sku/title/color",
+            })
+            continue
+
+        try:
+            image_path = find_image(images_root, sku, color)
+        except FileNotFoundError as exc:
+            results.append({"sku": sku, "status": "error", "message": str(exc)})
+            continue
+
+        if dry_run:
+            results.append({"sku": sku, "status": "dry_run", "message": "Skipped upload"})
+            continue
+
+        try:
+            image_url = upload_image(session, config, image_path)
+            payload = prepare_payload(template, mapping, sku, title, color, image_url, config)
+            response = submit_product(session, config, payload)
+            results.append({
+                "sku": sku,
+                "status": "uploaded",
+                "message": json.dumps(response)[:500],
+            })
+        except Exception as exc:  # noqa: BLE001
+            results.append({"sku": sku, "status": "error", "message": str(exc)})
+
+    return results
+
+
+def parse_args() -> argparse.Namespace:
+    parser = argparse.ArgumentParser(
+        description="Upload TEMU POD products by replacing the first image, SKU, and title.",
+    )
+    parser.add_argument("--spreadsheet", required=True, help="Excel or CSV file path")
+    parser.add_argument("--sku-column", required=True, help="Column name for SKU")
+    parser.add_argument("--title-column", required=True, help="Column name for Title")
+    parser.add_argument("--color-column", required=True, help="Column name for Color")
+    parser.add_argument("--images-root", required=True, help="Folder with SKU subfolders")
+    parser.add_argument("--config", required=True, help="JSON config for TEMU endpoints")
+    parser.add_argument("--dry-run", action="store_true", help="Validate without uploading")
+    parser.add_argument("--report", default="temu_upload_report.json")
+    return parser.parse_args()
+
+
+def main() -> None:
+    args = parse_args()
+    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
+
+    rows = load_rows(
+        Path(args.spreadsheet),
+        sku_column=args.sku_column,
+        title_column=args.title_column,
+        color_column=args.color_column,
+    )
+
+    results = process_rows(
+        rows,
+        images_root=Path(args.images_root),
+        config=config,
+        dry_run=args.dry_run,
+    )
+
+    report_path = Path(args.report)
+    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
+
+    success_count = sum(1 for item in results if item["status"] == "uploaded")
+    error_count = sum(1 for item in results if item["status"] == "error")
+    logging.info("Completed. Uploaded: %s | Errors: %s", success_count, error_count)
+    logging.info("Report written to %s", report_path)
+
+
+if __name__ == "__main__":
+    main()
