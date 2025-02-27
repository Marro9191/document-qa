import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go

# Custom CSS for better layout and styling
st.markdown("""
    <style>
    .main {
        padding-top: 20px;
    }
    .stButton>button {
        height: 2.2em;
        width: 5em;
        margin-left: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Add logo at the top-left corner
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Grok_%28logo%29.svg/1200px-Grok_%28logo%29.svg.png", width=100)  # Replace with your logo path or URL

# Show title and description (above responses)
st.title("📄 Document question answering with visualizations")
st.write(
    "Upload a document below and ask analytical questions "
    "Supported formats: .txt, .md, .csv, .xlsx. For Excel/CSV files, "
    "you can also visualize the data with customizable charts."
)

# Get OpenAI API key from Streamlit secrets (no UI input required)
try:
    openai_api_key = st.secrets["openai"]["api_key"]
    client = OpenAI(api_key=openai_api_key)
except KeyError:
    st.error("Please add your OpenAI API key to `.streamlit/secrets.toml` under the key `openai.api_key`. See https://docs.streamlit.io/develop/concepts/connections/secrets-management for instructions.")
    st.stop()

# Container for responses and visualizations (top section)
with st.container():
    if 'responses' not in st.session_state:
        st.session_state.responses = []

    # Display previous responses and visualizations
    for response in st.session_state.responses:
        st.subheader("GPT Response")
        st.write(response['text'])
        
        if 'visualization' in response:
            st.subheader("Data Visualizations")
            st.write("Data Table:")
            st.dataframe(response['visualization']['df'])
            
            if not response['visualization']['df'].empty:
                st.write("Generated Chart:")
                st.plotly_chart(response['visualization']['fig'])

# Container for file upload and chat input (bottom section)
with st.container():
    # Let the user upload a file first (no API key prompt in UI)
    uploaded_file = st.file_uploader(
        "Upload a document (.txt, .md, .csv, .xlsx)",
        type=("txt", "md", "csv", "xlsx")
    )

    # Chat input with "Send" button
    col1, col2 = st.columns([9, 1])  # Adjust width ratio as needed
    with col1:
        question = st.text_input(
            "Ask a question about the document...",
            placeholder="Can you give me a short summary?",
            disabled=not uploaded_file,
            key="question_input"
        )
    with col2:
        send_button = st.button("Send", disabled=not uploaded_file)

    if uploaded_file and (question or send_button):
        # Process the uploaded file based on its type
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df = None  # DataFrame for Excel/CSV
        
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

        # Collect the streamed response
        response_text = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response_text += chunk.choices[0].delta.content
        st.session_state.responses.append({'text': response_text})

        # If it's a data file (CSV/Excel), prepare visualization data
        visualization = None
        if df is not None:
            visualization = {
                'df': df.copy(),
                'fig': None
            }
            
            if not df.empty:
                # Default visualization (can be customized later via UI if needed)
                chart_type = "Bar"  # Default chart type
                x_col = df.columns[0]  # Default to first column
                numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    y_col = numeric_cols[0]  # Default to first numeric column
                    
                    # Default color (single color)
                    color = "#00f900"
                    
                    fig = go.Figure()
                    
                    if chart_type == "Bar":
                        fig.add_trace(go.Bar(x=df[x_col], y=df[y_col], marker_color=color))
                    
                    elif chart_type == "Line":
                        fig.add_trace(go.Scatter(x=df[x_col], y=df[y_col], mode='lines', line=dict(color=color)))
                    
                    elif chart_type == "Pie":
                        pie_data = df.groupby(x_col)[y_col].sum()
                        fig.add_trace(go.Pie(labels=pie_data.index, values=pie_data.values))
                    
                    elif chart_type == "Scatter":
                        fig.add_trace(go.Scatter(
                            x=df[x_col], 
                            y=df[y_col], 
                            mode='markers',
                            marker=dict(color=color, size=10)
                        ))
                    
                    elif chart_type == "Area":
                        fig.add_trace(go.Scatter(
                            x=df[x_col], 
                            y=df[y_col], 
                            fill='tozeroy',
                            line=dict(color=color)
                        ))

                    fig.update_layout(
                        title="Default Data Visualization",
                        xaxis_title=x_col,
                        yaxis_title=y_col,
                        height=500,
                        width=700
                    )
                    
                    visualization['fig'] = fig

        # Update session state with visualization if available
        if visualization:
            st.session_state.responses[-1]['visualization'] = visualization

        # Clear the input after sending
        st.session_state.question_input = ""

# Display a message if no file is uploaded
if not uploaded_file:
    st.write("Please upload a document to get started.")
