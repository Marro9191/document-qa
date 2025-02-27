import streamlit as st
from openai import OpenAI
import pandas as pd

# Show title and description.
st.title("📄 Document question answering")
st.write(
    "Upload a document below and ask a question about it – GPT will answer! "
    "To use this app, you need to provide an OpenAI API key, which you can get [here](https://platform.openai.com/account/api-keys). "
)

# Ask user for their OpenAI API key
openai_api_key = st.text_input("OpenAI API Key", type="password")
if not openai_api_key:
    st.info("Please add your OpenAI API key to continue.", icon="🗝️")
else:
    # Create an OpenAI client
    client = OpenAI(api_key=openai_api_key)

    # Let the user upload a file with expanded file types
    uploaded_file = st.file_uploader(
        "Upload a document (.txt, .md, .csv, .xlsx)", 
        type=("txt", "md", "csv", "xlsx")
    )

    # Ask the user for a question
    question = st.text_area(
        "Now ask a question about the document!",
        placeholder="Can you give me a short summary?",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:
        # Process the uploaded file based on its type
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension in ['txt', 'md']:
            document = uploaded_file.read().decode()
        elif file_extension == 'csv':
            df = pd.read_csv(uploaded_file)
            document = df.to_string()
        elif file_extension == 'xlsx':
            df = pd.read_excel(uploaded_file)
            document = df.to_string()
        else:
            st.error("Unsupported file format")
            st.stop()

        # Prepare the messages for OpenAI
        messages = [
            {
                "role": "user",
                "content": f"Here's a document: {document} \n\n---\n\n {question}",
            }
        ]

        # Generate an answer using the OpenAI API
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True,
        )

        # Stream the response to the app
        st.write_stream(stream)
