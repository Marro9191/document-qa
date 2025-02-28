import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
import re
import datetime

# Sidebar Navigation
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Menu", ["Insight Conversation"])

if menu == "Insight Conversation":
    st.title("📄 Comcore Prototype v2")
    st.write("Upload a CSV or Excel file and ask analytical questions. The system will automatically generate insights and visualizations.")

    # OpenAI API Key Setup
    try:
        openai_api_key = st.secrets["openai"]["api_key"]
        client = OpenAI(api_key=openai_api_key)
    except KeyError:
        st.error("Please add your OpenAI API key in Streamlit secrets.")
        st.stop()

    # File Uploader
    uploaded_file = st.file_uploader("Upload CSV or Excel File", type=("csv", "xlsx"))

    # User Question Input
    question = st.text_area("Ask a question about the data:", disabled=not uploaded_file)

    if uploaded_file and question:
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df = pd.read_csv(uploaded_file) if file_extension == 'csv' else pd.read_excel(uploaded_file)
        document = df.to_string()

        # OpenAI Query
        messages = [{"role": "user", "content": f"Here's a document: {document}\n\n---\n\n {question}"}]
        stream = client.chat.completions.create(model="gpt-4", messages=messages, stream=True)
        response_text = "".join(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)

        # Display Response
        st.subheader("Response")
        st.write(response_text)

        # Automatic Column Detection
        date_col, numeric_col, category_col = None, None, None
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]) or "date" in col.lower():
                date_col = col
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_col = col
            if df[col].dtype == 'object':
                category_col = col

        if date_col and numeric_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce').dt.strftime('%Y-%m')
            filtered_df = df.groupby(date_col)[numeric_col].sum().reset_index()
            
            # Extract Labels and Numbers from Response
            labels = re.findall(r'\b[A-Za-z]+\b', response_text)
            numbers = [int(n) for n in re.findall(r'\b\d+\b', response_text)]
            parsed_data = {label: numbers[i] for i, label in enumerate(labels) if i < len(numbers)}
            
            # Match Response Data with Uploaded Data
            matched_data = {row[date_col]: row[numeric_col] for _, row in filtered_df.iterrows() if row[date_col] in parsed_data}
            
            # Dynamic Chart Type Selection
            chart_type = "Bar"
            if "trend" in question.lower() or "over time" in question.lower():
                chart_type = "Line"
            elif "distribution" in question.lower():
                chart_type = "Pie"

            # Generate Chart
            fig = go.Figure()
            if chart_type == "Bar":
                fig.add_trace(go.Bar(x=list(matched_data.keys()), y=list(matched_data.values()), marker_color="#00f900"))
            elif chart_type == "Line":
                fig.add_trace(go.Scatter(x=list(matched_data.keys()), y=list(matched_data.values()), mode='lines', line=dict(color="#00f900")))
            elif chart_type == "Pie":
                fig.add_trace(go.Pie(labels=list(matched_data.keys()), values=list(matched_data.values())))

            # Display Chart
            fig.update_layout(title=f"{numeric_col.capitalize()} Trends", height=500, width=700)
            st.plotly_chart(fig)
        else:
            st.warning("No suitable data available for visualization.")
