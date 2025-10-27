import streamlit as st
import requests
from PIL import Image
from io import BytesIO
import json
import time

# Set page config
st.set_page_config(
    page_title="Meme Generator",
    page_icon="🎯",
    layout="wide"
)

# Constants
# Use the public API endpoint instead of localhost
BASE_URL = "https://api.memegen.link"
SUPPORTED_FORMATS = ["png", "jpg", "gif", "webp"]

# Initialize session state for caching
if 'templates_cache' not in st.session_state:
    st.session_state.templates_cache = None
if 'last_cache_time' not in st.session_state:
    st.session_state.last_cache_time = None

def load_templates():
    """Load all available meme templates with caching"""
    try:
        # Check if we have cached templates and they're less than 1 hour old
        current_time = time.time()
        if (st.session_state.templates_cache is not None and 
            st.session_state.last_cache_time is not None and 
            current_time - st.session_state.last_cache_time < 3600):
            return st.session_state.templates_cache

        # First try /templates endpoint
        response = requests.get(f"{BASE_URL}/templates", timeout=10)
        if response.status_code == 200:
            templates = response.json()
            if templates:
                # Cache the templates
                st.session_state.templates_cache = templates
                st.session_state.last_cache_time = current_time
                return templates
        
        # If /templates fails or returns empty, try /images endpoint
        response = requests.get(f"{BASE_URL}/images", timeout=10)
        if response.status_code == 200:
            examples = response.json()
            # Create template list from examples
            templates_set = set()
            templates = []
            for example in examples:
                template_id = example['template']['id']
                if template_id not in templates_set:
                    templates_set.add(template_id)
                    templates.append({
                        'id': template_id,
                        'name': template_id.replace('-', ' ').title(),
                        'lines': 2
                    })
            # Cache the templates
            st.session_state.templates_cache = templates
            st.session_state.last_cache_time = current_time
            return templates
        
        st.error(f"Failed to load templates. Status code: {response.status_code}")
        return []
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Could not connect to the meme API. Please check your internet connection.")
        return []
    except requests.exceptions.Timeout:
        st.error("⚠️ Connection timed out. Please try again.")
        return []
    except Exception as e:
        st.error(f"⚠️ Error loading templates: {str(e)}")
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
        with st.spinner("Generating meme..."):
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return BytesIO(response.content)
            elif response.status_code == 404:
                st.error("Template not found. Please try another template.")
            else:
                st.error(f"Failed to generate meme. Status code: {response.status_code}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Could not connect to the meme API. Please check your internet connection.")
        return None
    except requests.exceptions.Timeout:
        st.error("⚠️ Request timed out. Please try again.")
        return None
    except Exception as e:
        st.error(f"⚠️ Error generating meme: {str(e)}")
        return None

def main():
    st.title("🎯 Meme Generator")
    st.markdown("Create custom memes with various templates and styles!")

    # Load templates with error handling
    with st.spinner("Loading templates..."):
        templates = load_templates()
        if not templates:
            st.error("⚠️ Could not load templates. Please make sure the backend server is running at " + BASE_URL)
            st.info("To start the backend server, run: poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 5000")
            return
    
    # Sidebar
    st.sidebar.header("Meme Configuration")
    
    # Template selection with search
    if templates:
        # Create template dictionary
        template_dict = {template.get('name', template.get('id', '')).title(): template['id'] 
                        for template in templates}
        
        # Add search box for templates
        search_term = st.sidebar.text_input("🔍 Search Templates", "").lower()
        
        # Filter templates based on search
        filtered_templates = {name: tid for name, tid in template_dict.items() 
                            if search_term in name.lower() or search_term in tid.lower()}
        
        if not filtered_templates:
            st.sidebar.warning("No templates match your search.")
            selected_template = None
        else:
            selected_template = st.sidebar.selectbox(
                "Choose a template",
                options=list(filtered_templates.keys()),
                index=0
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