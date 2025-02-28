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
        "Supported formats: .txt, .md, .csv, .xlsx. "
        "You can also visualize the data with customizable charts. "
        "Please note it has to be UTF-8 encoded. "
    )

    # Get OpenAI API key from Streamlit secrets (no UI input required)
    try:
        openai_api_key = st.secrets["openai"]["api_key"]
        client = OpenAI(api_key=openai_api_key)
    except KeyError:
        st.error("Please add your OpenAI API key to `.streamlit/secrets.toml` under the key `openai.api_key`. See https://docs.streamlit.io/develop/concepts/connections/secrets-management for instructions.")
        st.stop()

    # Let the user upload a file first (no API key prompt in UI)
    uploaded_file = st.file_uploader(
        "Upload a document (.txt, .md, .csv, .xlsx)",
        type=("txt", "md", "csv", "xlsx")
    )

    # Ask the user for a question only after a file is uploaded
    question = st.text_area(
        "Now ask a question about the document!",
        placeholder="For example: What were total number of reviews last month compared to this month for any category? Give me totals for each month only.",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:
        # Process the uploaded file based on its type
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df = None  # DataFrame for Excel/CSV
        
        if file_extension in ['txt', 'md']:
            document = uploaded_file.read().decode()
        
        elif file_extension == 'csv':
            df = pd.read_csv(uploaded_file, encoding='utf-8')
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

        # Display the response
        st.subheader("Response")
        st.write(response_text)

        # If it's a data file (CSV/Excel), offer visualization options
        if df is not None:
            st.subheader("Data Visualizations")
            
            # Filter data table and generate visualizations based on OpenAI response dynamically
            show_full_table = "full table" in question.lower() or "all data" in question.lower()
            
            if show_full_table:
                # Show full table if explicitly requested
                st.write("Full Data Table:")
                st.dataframe(df)
            else:
                # Dynamically parse the OpenAI response to extract data points
                parsed_data = {}
                labels = re.findall(r'[A-Za-z]+\s*\d*', response_text)  # Extract labels (e.g., months, categories)
                numbers = re.findall(r'\d+', response_text)  # Extract numbers (totals)

                # Match labels and numbers, assuming numbers follow labels in the response
                if labels and numbers:
                    for i in range(min(len(labels), len(numbers))):
                        label = labels[i].strip().capitalize()
                        value = int(numbers[i])
                        parsed_data[label] = value

                # Identify relevant columns in the DataFrame based on response and query
                keywords = question.lower().split()
                date_col = None
                numeric_col = None
                category_col = None

                # Identify date, numeric, and category columns dynamically
                for col in df.columns:
                    if any(keyword in col.lower() for keyword in keywords + ['date', 'time']):
                        date_col = col
                    if pd.api.types.is_numeric_dtype(df[col]) and any(keyword in col.lower() for keyword in keywords + ['number', 'count', 'total', 'value', 'review']):
                        numeric_col = col
                    if 'category' in col.lower():
                        category_col = col

                # Filter data based on identified columns and date if available
                filtered_df = df.copy()
                if date_col and numeric_col:
                    # Filter for relevant category if mentioned in query or response
                    if any('category' in q.lower() for q in keywords) or any(label.lower() in response_text.lower() for label in labels if label):
                        if category_col and category_col in df.columns:
                            # Try to match any category mentioned in response or query
                            for label in labels:
                                if label.lower() in response_text.lower():
                                    category_value = label.lower()
                                    filtered_df = filtered_df[filtered_df[category_col].str.lower() == category_value].copy()
                                    break
                            if filtered_df.empty and 'toothbrush' in question.lower():
                                filtered_df = filtered_df[filtered_df[category_col].str.lower() == 'toothbrush'].copy()

                    # Convert date column to datetime with flexible format
                    try:
                        filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], format='%d/%m/%y', errors='coerce').dt.strftime('%Y-%m')
                        # Group by month and sum the numeric column
                        filtered_df = filtered_df.groupby(date_col)[numeric_col].sum().reset_index()
                    except (ValueError, TypeError) as e:
                        st.warning(f"Could not parse date column '{date_col}' due to: {e}. Trying auto-detection.")
                        # Try auto-detection if DD/MM/YY fails
                        filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce').dt.strftime('%Y-%m') if pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]) else filtered_df[date_col]
                        if pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]):
                            filtered_df = filtered_df.groupby(date_col)[numeric_col].sum().reset_index()

                # Display only relevant data table if data is filtered
                if not filtered_df.empty:
                    st.write("Relevant Data Table (including dates and numeric data if available):")
                    st.write("Debug: Filtered DataFrame columns:", filtered_df.columns.tolist())  # Debugging output
                    st.dataframe(filtered_df)
                else:
                    st.warning("No relevant data found for the query based on the response.")

                # Dynamically generate the most relevant graph based on the OpenAI response and data
                if not filtered_df.empty and date_col and numeric_col:
                    # Map response labels to DataFrame data for comparison
                    response_labels = list(parsed_data.keys())
                    df_values = filtered_df[date_col].unique().tolist()
                    df_numeric_values = filtered_df[numeric_col].tolist()

                    # Match response labels (e.g., months) to DataFrame months
                    chart_data = {}
                    for label in response_labels:
                        # Convert label to month format (e.g., "January" -> "2025-01")
                        try:
                            month_str = pd.to_datetime(label, format='%B', errors='coerce').strftime('%Y-%m')
                            if month_str in df_values:
                                idx = df_values.index(month_str)
                                chart_data[label] = df_numeric_values[idx]
                        except (ValueError, TypeError):
                            # If label isn't a month, try direct matching (e.g., categories)
                            if label.lower() in [str(val).lower() for val in df_values]:
                                idx = [str(val).lower() for val in df_values].index(label.lower())
                                chart_data[label] = df_numeric_values[idx]

                    if chart_data:
                        # Determine the most relevant chart type based on query and response
                        chart_type = "Bar"  # Default to bar for comparisons (e.g., last month vs. this month)
                        if any(keyword in question.lower() for keyword in ["trend", "over time", "monthly", "daily"]):
                            chart_type = "Line"
                        elif any(keyword in question.lower() for keyword in ["distribution", "percentage", "proportion"]):
                            chart_type = "Pie"

                        # Generate the dynamic chart
                        fig = go.Figure()
                        if chart_type == "Bar":
                            fig.add_trace(go.Bar(
                                x=list(chart_data.keys()),
                                y=list(chart_data.values()),
                                marker_color="#00f900"  # Default green color, matching your earlier examples
                            ))
                        elif chart_type == "Line":
                            fig.add_trace(go.Scatter(
                                x=list(chart_data.keys()),
                                y=list(chart_data.values()),
                                mode='lines',
                                line=dict(color="#00f900")
                            ))
                        elif chart_type == "Pie":
                            fig.add_trace(go.Pie(
                                labels=list(chart_data.keys()),
                                values=list(chart_data.values())
                            ))

                        # Update layout with labeled axes and dynamic title
                        title = f"Comparison of {numeric_col.capitalize()} by {date_col}"
                        if chart_type == "Pie":
                            title = f"Distribution of {numeric_col.capitalize()}"
                        fig.update_layout(
                            title=title,
                            xaxis_title=date_col if chart_type != "Pie" else None,
                            yaxis_title=numeric_col.capitalize() if chart_type != "Pie" else None,
                            height=500,
                            width=700
                        )
                        
                        st.plotly_chart(fig)
                    else:
                        st.warning("Could not match response data to DataFrame for visualization.")
                else:
                    st.warning("No suitable data available for visualization based on the response.")
