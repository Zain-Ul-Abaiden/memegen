import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import json

# Set page config
st.set_page_config(
    page_title="Meme Generator",
    page_icon="🎯",
    layout="wide"
)

# Constants
BASE_URL = "http://localhost:5000"
SUPPORTED_FORMATS = ["png", "jpg", "gif", "webp"]

def load_templates():
    """Load all available meme templates"""
    try:
        response = requests.get(f"{BASE_URL}/templates")
        if response.status_code == 200:
            return response.json()
        return []
    except:
        return []

def generate_meme(template_id, text_lines, output_format="png", width=None, height=None):
    """Generate a meme using the API"""
    # Convert spaces to underscores and handle special characters
    processed_lines = [line.replace(" ", "_").replace("-", "--") for line in text_lines]
    
    # Construct URL
    url = f"{BASE_URL}/images/{template_id}/{'/'.join(processed_lines)}.{output_format}"
    
    # Add dimension parameters if provided
    params = {}
    if width:
        params['width'] = width
    if height:
        params['height'] = height
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return BytesIO(response.content)
        return None
    except:
        return None

def main():
    st.title("🎯 Meme Generator")
    st.markdown("Create custom memes with various templates and styles!")

    # Load templates
    templates = load_templates()
    
    # Sidebar
    st.sidebar.header("Meme Configuration")
    
    # Template selection
    template_dict = {template['name']: template['id'] for template in templates}
    selected_template = st.sidebar.selectbox(
        "Choose a template",
        options=list(template_dict.keys()),
        index=0 if template_dict else None
    )

    # Text input
    st.sidebar.subheader("Text Lines")
    text1 = st.sidebar.text_input("Top Text", "")
    text2 = st.sidebar.text_input("Bottom Text", "")
    
    # Format selection
    output_format = st.sidebar.selectbox(
        "Output Format",
        SUPPORTED_FORMATS,
        index=0
    )
    
    # Dimension inputs
    st.sidebar.subheader("Dimensions (Optional)")
    width = st.sidebar.number_input("Width", min_value=0, max_value=2000, value=0, step=50)
    height = st.sidebar.number_input("Height", min_value=0, max_value=2000, value=0, step=50)
    
    # Generate button
    if st.sidebar.button("Generate Meme"):
        if selected_template and (text1 or text2):
            template_id = template_dict[selected_template]
            text_lines = [line for line in [text1, text2] if line]
            
            # Generate meme
            meme_bytes = generate_meme(
                template_id,
                text_lines,
                output_format,
                width if width > 0 else None,
                height if height > 0 else None
            )
            
            if meme_bytes:
                # Display the generated meme
                st.image(meme_bytes, caption="Generated Meme")
                
                # Download button
                st.download_button(
                    label="Download Meme",
                    data=meme_bytes,
                    file_name=f"meme.{output_format}",
                    mime=f"image/{output_format}"
                )
            else:
                st.error("Failed to generate meme. Please try again.")
        else:
            st.warning("Please select a template and enter at least one line of text.")

    # Display template preview
    if selected_template:
        st.sidebar.subheader("Template Preview")
        template_id = template_dict[selected_template]
        preview_url = f"{BASE_URL}/images/{template_id}/preview/image.png"
        try:
            response = requests.get(preview_url)
            if response.status_code == 200:
                st.sidebar.image(BytesIO(response.content), width=200)
        except:
            st.sidebar.error("Failed to load template preview")

if __name__ == "__main__":
    main()