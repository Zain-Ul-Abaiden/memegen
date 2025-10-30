import google.generativeai as genai

genai.configure(api_key="AIzaSyB3wwPkBfVqGYPbEyBVHPC9a1Hf5qPGjI8")

try:
    model = genai.GenerativeModel('gemini-2.0-flash')
    response = model.generate_content("Say hello world.")
    print(response.text)
except Exception as e:
    print("ERROR:", e)