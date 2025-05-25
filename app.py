import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
import io
import base64
import numpy as np
import openai
import hashlib
import tempfile
import os
from supabase import create_client, Client

st.set_page_config(page_title="AI Shirt Tool", layout="wide")
st.title("🛠️ AI Shirt Tools")

# Mode selection
app_mode = st.sidebar.selectbox("Select Application", [
    "👕 T-Shirt Title Generator"
])

# Supabase config
SUPABASE_URL = "https://hryhwjkwpgzwxxhpnjwa.supabase.co"
SUPABASE_KEY = st.secrets.get("supabase_key")
BUCKET_NAME = "images"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# OpenAI API key
api_key = st.secrets.get("openai_api_key")

if app_mode == "👕 T-Shirt Title Generator":
    st.header("👕 AI Shirt Name Generator")

    if not api_key:
        st.warning("👈 Please set your OpenAI API key in Streamlit Secrets as `openai_api_key`.")
    else:
        openai.api_key = api_key

        # Expanded color options
        shirt_color = st.selectbox("👕 Shirt Color:", [
            "Black", "White", "Grey", "Red", 
            "Blue", "Green", "Yellow", "Pink", "Purple", 
            "Orange", "Brown", "Beige", "Navy", "Teal"
        ])

        # Expanded clothing type options
        shirt_type = st.selectbox("👗 Clothing Type:", [
            "T-Shirt", "Crop Top", "Tank Top", 
            "Hoodie", "Sweatshirt", "Long Sleeve", "Polo Shirt"
        ])

        shirt_gender = st.radio("🫍 Gender:", ["Men", "Women"], horizontal=True)
        descriptor_word = st.text_input("✨ Custom Word for Shirt Title (e.g., 'Pure', 'Luck', 'Urban')", value="Pure")
        custom_keyword = st.text_input("🔑 Custom Keyword at the End (optional)", value="")

        # Preview of example title
        example_preview = f"{shirt_gender}'s {descriptor_word} - Cotton {shirt_color} {shirt_type}: \"AI-Generated Design\" - {custom_keyword if custom_keyword else ''}"
        st.markdown(f"**Preview Example:** _{example_preview}_")

        uploaded_files = st.file_uploader("Upload T-shirt design images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        if uploaded_files:  # Check if files are uploaded
            def preprocess_image(image: Image.Image, color: str) -> Image.Image:
                gray = ImageOps.grayscale(image)
                np_img = np.array(gray)
                # List of dark colors where enhancement is needed
                dark_colors = ["Black", "Navy", "Brown", "Purple"]
                
                if color in dark_colors:
                    contrast = ImageEnhance.Contrast(gray).enhance(2.5)
                    inverted = ImageOps.invert(contrast)
                    return inverted.convert("RGB")
                else:
                    white_ratio = (np_img > 220).sum() / np_img.size
                    if white_ratio > 0.75:
                        contrast = ImageEnhance.Contrast(gray).enhance(2.5)
                        inverted = ImageOps.invert(contrast)
                        return inverted.convert("RGB")
                return image

            def encode_image(image: Image.Image, color: str) -> str:
                image = preprocess_image(image, color)
                buffered = io.BytesIO()
                image.save(buffered, format="PNG")
                return base64.b64encode(buffered.getvalue()).decode()

            def generate_title_with_gpt(image_b64: str, gender: str, color: str, type: str) -> str:
                def call_gpt(prompt_text):
                    messages = [
                        {
                            "role": "system",
                            "content": "You're a creative product copywriter for a fashion brand. Write short, stylish, eye-catching T-shirt product titles from image designs."
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt_text},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                            ]
                        }
                    ]
                    response = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        max_tokens=100
                    )
                    return response.choices[0].message.content.strip()

                prompt = f"Generate a detailed and stylish product title for a {color.lower()} cotton {type} for {gender.lower()}s. Base the title on the printed artwork in the image."
                result = call_gpt(prompt)

                if "can't help" in result.lower() or "i'm sorry" in result.lower():
                    fallback_prompt = f"Write a trendy product title for the {type} shown in the image."
                    result = call_gpt(fallback_prompt)

                return result

            def sanitize_title(title: str) -> str:
                # Replace accented Spanish letters manually
                replacements = {
                    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
                    'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U'
                }

                # Replace accented letters
                for accented_char, plain_char in replacements.items():
                    title = title.replace(accented_char, plain_char)

                # Remove all symbols except '-' and ':'
                sanitized = ''.join(char if char.isalnum() or char in ['-', ':', ' '] else '' for char in title)

                return sanitized

            results = []
            with st.spinner("🧐 Generating creative product titles with GPT-4 Vision..."):
                for file in uploaded_files:
                    img = Image.open(file).convert("RGB")
                    try:
                        img_b64 = encode_image(img, shirt_color)  # Pass shirt_color here
                        title = generate_title_with_gpt(img_b64, shirt_gender, shirt_color, shirt_type)
                        full_title = f"{shirt_gender}'s {descriptor_word} - Cotton {shirt_color} {shirt_type}: \"{title}\""
                        if custom_keyword:
                            full_title += f" - {custom_keyword}"

                        sanitized_title = sanitize_title(full_title)
                        results.append(sanitized_title)
                    except Exception as e:
                        results.append(f"ERROR: {e}")

            st.success("✅ All titles generated!")
            st.text_area("📝 Generated T-Shirt Titles", "\n".join(results), height=300)

        else:
            st.warning("Please upload at least one image to generate titles.")
