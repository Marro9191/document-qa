import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
import re

# Add sidebar with menu item
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Menu", ["Insight Conversation"])

# Show title and description (main area)
if menu == "Insight Conversation":
    st.title("📄 Comcore Prototype v1")
    st.write(
        "Upload CSV file below and ask analytical questions. "
        "Supported formats: .txt, .md, .csv, .xlsx., "
        "and you can also visualize the data with customizable charts. "
        "Please note it has to be UTF 8 encoded. "
    )

    # Get OpenAI API key from Streamlit secrets (no UI input required)
    try:
        openai_api_key = st.secrets["openai"]["api_key"]
        client = OpenAI(api_key=openai_api_key)
    except KeyError:
        st.error("Please add your OpenAI API key to `.streamlit/secrets.toml` under the key `openai.api_key`. See https://docs.streamlit.io/develop/concepts/connections/secrets-management for instructions.")
        st.stop()

    # Let the user upload a file first (no UI input required)
    uploaded_file = st.file_uploader(
        "Upload a document (.txt, .md, .csv, .xlsx)",
        type=("txt", "md", "csv", "xlsx")
    )

    # Ask the user for a question only after a file is uploaded
    question = st.text_area(
        "Now ask a question about the document!",
        placeholder="For example: What were total number of reviews last month compared to this month for toothbrush category? Give me total for each month only.",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:
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

        # Collect the streamed response into a string
        response = ""
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content

        # Display the response
        st.subheader("Response")
        st.write(response)

        # If it's a data file (CSV/Excel), attempt to show only relevant data
        if df is not None:
            # Try to parse the response and question to filter the DataFrame
            relevant_df = None
            try:
                # Simple parsing: look for column names or conditions in the question/response
                question_lower = question.lower()
                response_lower = response.lower()
                
                # Extract potential column names from the question (assuming they match df.columns)
                potential_cols = [col for col in df.columns if col.lower() in question_lower]
                
                if potential_cols:
                    # Start with a basic filter based on the question
                    relevant_df = df[potential_cols].copy()
                    
                    # Look for conditions like "last month," "this month," "toothbrush category," etc.
                    if "month" in question_lower:
                        if "date" in df.columns or "month" in df.columns:
                            # Assume a date or month column exists and filter for recent months
                            if "date" in df.columns:
                                df['date'] = pd.to_datetime(df['date'])
                                recent_months = df[df['date'].dt.month >= (df['date'].dt.month.max() - 1)]
                                relevant_df = relevant_df.merge(recent_months, how='inner')
                            elif "month" in df.columns:
                                recent_months = df[df['month'].isin(['January', 'February'])]  # Example, adjust as needed
                                relevant_df = relevant_df.merge(recent_months, how='inner')
                    
                    if "toothbrush" in question_lower and "category" in question_lower:
                        if "category" in df.columns:
                            relevant_df = relevant_df[relevant_df['category'].str.contains("toothbrush", case=False, na=False)]

                # If no relevant data is found, check if the response implies a summary or aggregation
                if relevant_df is None or relevant_df.empty:
                    # Look for numeric summaries in the response (e.g., totals, counts)
                    numbers = re.findall(r'\d+', response)
                    if numbers and potential_cols:
                        # Create a small summary table if possible
                        summary_data = {col: [int(num) if num.isdigit() else 0 for num in numbers[:len(potential_cols)]] for col in potential_cols}
                        relevant_df = pd.DataFrame(summary_data)
                
                # Display relevant data if available
                if relevant_df is not None and not relevant_df.empty:
                    st.subheader("Relevant Data Table")
                    st.dataframe(relevant_df)
                else:
                    st.warning("No specific data table available for this query. Showing only the response above.")

            except Exception as e:
                st.error(f"Error processing data table for query: {e}")
                st.warning("No specific data table available for this query. Showing only the response above.")

            # Visualization options (unchanged, but only shown if relevant data exists)
            if not df.empty:
                st.subheader("Data Visualizations")
                st.write("Generate a chart:")
                chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter", "Area"])
                x_col = st.selectbox("X-axis", df.columns)
                numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
                
                if len(numeric_cols) > 0:
                    y_col = st.selectbox("Y-axis", numeric_cols)
                    
                    # Color options
                    color_option = st.selectbox("Color by", ["Single Color"] + df.columns.tolist())
                    if color_option == "Single Color":
                        color = st.color_picker("Pick a color", "#00f900")
                    else:
                        color = color_option

                    # Chart customization
                    chart_title = st.text_input("Chart Title", "Data Visualization")
                    
                    if st.button("Generate Chart"):
                        fig = go.Figure()
                        
                        if chart_type == "Bar":
                            fig.add_trace(go.Bar(x=df[x_col], y=df[y_col], marker_color=color if color_option == "Single Color" else None))
                        
                        elif chart_type == "Line":
                            fig.add_trace(go.Scatter(x=df[x_col], y=df[y_col], mode='lines', line=dict(color=color if color_option == "Single Color" else None)))
                        
                        elif chart_type == "Pie":
                            pie_data = df.groupby(x_col)[y_col].sum()
                            fig.add_trace(go.Pie(labels=pie_data.index, values=pie_data.values))
                        
                        elif chart_type == "Scatter":
                            fig.add_trace(go.Scatter(
                                x=df[x_col], 
                                y=df[y_col], 
                                mode='markers',
                                marker=dict(
                                    color=df[color] if color_option != "Single Color" else color,
                                    size=10
                                )
                            ))
                        
                        elif chart_type == "Area":
                            fig.add_trace(go.Scatter(
                                x=df[x_col], 
                                y=df[y_col], 
                                fill='tozeroy',
                                line=dict(color=color if color_option == "Single Color" else None)
                            ))

                        # Update layout
                        fig.update_layout(
                            title=chart_title,
                            xaxis_title=x_col,
                            yaxis_title=y_col,
                            height=500,
                            width=700
                        )
                        
                        st.plotly_chart(fig)
                else:
                    st.warning("No numeric columns available for charting.")
            else:
                st.warning("The uploaded data is empty.")
