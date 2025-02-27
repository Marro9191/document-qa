import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go

# Show title and description
st.title("📄 Document question answering with visualizations")
st.write(
    "Upload a document below and ask a question about it – GPT will answer! "
    "Supported formats: .txt, .md, .csv, .xlsx. For Excel/CSV files, "
    "a pie chart will automatically be generated for Toothbrush reviews."
)

# Ask user for their OpenAI API key
openai_api_key = st.text_input("OpenAI API Key", type="password")
if not openai_api_key:
    st.info("Please add your OpenAI API key to continue.", icon="🗝️")
else:
    # Create an OpenAI client
    client = OpenAI(api_key=openai_api_key)

    # Let the user upload a file
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
        df = None
        
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

        # Create the message with the document content and question
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

        # Display the response
        st.subheader("GPT Response")
        st.write_stream(stream)

        # If it's a data file (CSV/Excel), automatically generate a pie chart for Toothbrush reviews
        if df is not None:
            st.subheader("Data Visualizations")
            
            # Display the table
            st.write("Data Table:")
            st.dataframe(df)

            # Filter for Toothbrush category and count reviews by month (January and February 2025)
            toothbrush_data = df[df['Category'] == 'Toothbrush']
            if not toothbrush_data.empty:
                # Group by date (assuming date format allows month extraction) and count reviews
                toothbrush_data['Month'] = pd.to_datetime(toothbrush_data['Date']).dt.strftime('%B %Y')
                monthly_reviews = toothbrush_data.groupby('Month')['Reviews'].sum()
                
                # Filter for January and February 2025
                january_reviews = monthly_reviews.get('January 2025', 0)
                february_reviews = monthly_reviews.get('February 2025', 0)
                
                # Prepare data for pie chart
                labels = ['January 2025', 'February 2025']
                values = [january_reviews, february_reviews]
                
                # Create pie chart
                fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3)])
                fig.update_layout(
                    title="Toothbrush Reviews Distribution (Jan 2025 vs Feb 2025)",
                    height=500,
                    width=700
                )
                
                st.plotly_chart(fig)
            else:
                st.warning("No Toothbrush category data found in the uploaded file.")
