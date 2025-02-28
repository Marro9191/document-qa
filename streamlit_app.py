import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go

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

        # Display the response
        st.subheader("Response")
        st.write_stream(stream)

        # If it's a data file (CSV/Excel), offer visualization options
        if df is not None:
            st.subheader("Data Visualizations")
            
            # Filter data table based on user query (e.g., Toothbrush, reviews, date)
            filtered_df = df.copy()
            show_full_table = "full table" in question.lower() or "all data" in question.lower()
            
            if show_full_table:
                # Show full table if explicitly requested
                st.write("Full Data Table:")
                st.dataframe(df)
            else:
                # Filter for relevant data only
                keywords = question.lower().split()
                relevant_columns = []
                date_col = None
                numeric_col = None

                # Identify relevant columns based on query keywords
                for col in df.columns:
                    if any(keyword in col.lower() for keyword in keywords):
                        relevant_columns.append(col)
                    if 'date' in col.lower():
                        date_col = col
                    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
                    if numeric_cols.any():
                        for num_col in numeric_cols:
                            if any(keyword in num_col.lower() for keyword in keywords):
                                numeric_col = num_col
                                break
                        if numeric_col:
                            break

                # Filter data based on identified columns and date if available
                if relevant_columns or date_col or numeric_col:
                    if date_col:
                        if date_col in df.columns and not df[date_col].isnull().all():
                            try:
                                filtered_df = df[[col for col in [date_col] + relevant_columns if col in df.columns]]
                                # Try to convert date column to datetime with error handling
                                filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce').dt.strftime('%Y-%m')
                            except (ValueError, TypeError) as e:
                                st.warning(f"Could not parse date column '{date_col}' due to: {e}. Using original format.")
                                filtered_df = df[[col for col in [date_col] + relevant_columns if col in df.columns]]
                        else:
                            st.warning(f"Date column '{date_col}' not found or is empty.")
                    else:
                        filtered_df = df[relevant_columns] if relevant_columns else df

                    # If numeric column is identified, aggregate or filter further
                    if numeric_col and date_col:
                        if not filtered_df[date_col].isnull().all() and numeric_col in filtered_df.columns:
                            try:
                                filtered_df = filtered_df.groupby(date_col)[numeric_col].sum().reset_index()
                            except KeyError as e:
                                st.warning(f"Error grouping by date and numeric column: {e}")
                    elif numeric_col:
                        filtered_df = filtered_df[[numeric_col] + relevant_columns]

                # Display only relevant data table
                if not filtered_df.empty:
                    st.write("Relevant Data Table (including dates if available):")
                    st.dataframe(filtered_df)
                else:
                    st.warning("No relevant data found for the query.")

            # Dynamically generate the most relevant graph based on the query
            if not filtered_df.empty:
                numeric_cols = filtered_df.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    # Determine the most relevant chart type and data based on the query
                    x_col = None
                    y_col = None
                    chart_type = None
                    title = "Data Visualization"
                    color = "#00f900"  # Default green color

                    # Find date column if available
                    date_cols = [col for col in filtered_df.columns if 'date' in col.lower()]
                    date_col = date_cols[0] if date_cols else None

                    # Find numeric columns mentioned in the query
                    for col in numeric_cols:
                        if any(keyword in col.lower() for keyword in question.lower().split()):
                            y_col = col
                            break

                    # Set X-axis (prefer date if available, otherwise first non-numeric column)
                    if date_col:
                        if not filtered_df[date_col].isnull().all():
                            try:
                                filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce').dt.strftime('%Y-%m')
                                x_col = date_col
                            except (ValueError, TypeError) as e:
                                st.warning(f"Could not format date column '{date_col}' for chart: {e}. Using original format.")
                                x_col = date_col
                        else:
                            x_col = date_col  # Use original format if datetime conversion fails
                    else:
                        non_numeric_cols = [col for col in filtered_df.columns if col not in numeric_cols]
                        x_col = non_numeric_cols[0] if non_numeric_cols else filtered_df.columns[0]

                    # Default to first numeric column if no specific numeric column is mentioned
                    if not y_col:
                        y_col = numeric_cols[0]

                    # Determine chart type based on query
                    if date_col and y_col and any(keyword in question.lower() for keyword in ["trend", "over time", "monthly", "daily"]):
                        chart_type = "Line"  # Time-series data
                        title = f"{y_col} Trend Over {x_col}"
                    elif date_col and y_col and any(keyword in question.lower() for keyword in ["compare", "comparison", "vs"]):
                        chart_type = "Bar"  # Comparison over time
                        title = f"{y_col} vs {x_col}"
                    elif any(keyword in question.lower() for keyword in ["distribution", "percentage", "proportion"]):
                        chart_type = "Pie"  # Categorical or percentage data
                        x_col = filtered_df.columns[0]  # Use first column for categories
                        y_col = numeric_cols[0]  # Use first numeric for values
                        title = f"Distribution of {y_col} by {x_col}"
                    elif y_col and x_col:
                        chart_type = "Bar"  # Default to Bar for other numeric comparisons
                        title = f"{x_col} vs {y_col}"

                    # Generate the dynamic chart if chart type is determined
                    if chart_type and x_col and y_col and x_col in filtered_df.columns and y_col in filtered_df.columns:
                        fig = go.Figure()
                        if chart_type == "Bar":
                            fig.add_trace(go.Bar(x=filtered_df[x_col], y=filtered_df[y_col], marker_color=color))
                        
                        elif chart_type == "Line":
                            fig.add_trace(go.Scatter(x=filtered_df[x_col], y=filtered_df[y_col], mode='lines', line=dict(color=color)))
                        
                        elif chart_type == "Pie":
                            pie_data = filtered_df.groupby(x_col)[y_col].sum()
                            fig.add_trace(go.Pie(labels=pie_data.index, values=pie_data.values))
                        
                        elif chart_type == "Scatter":
                            fig.add_trace(go.Scatter(
                                x=filtered_df[x_col], 
                                y=filtered_df[y_col], 
                                mode='markers',
                                marker=dict(color=color, size=10)
                            ))
                        
                        elif chart_type == "Area":
                            fig.add_trace(go.Scatter(
                                x=filtered_df[x_col], 
                                y=filtered_df[y_col], 
                                fill='tozeroy',
                                line=dict(color=color)
                            ))

                        # Update layout with labeled axes and dynamic title
                        fig.update_layout(
                            title=title,
                            xaxis_title=x_col,
                            yaxis_title=y_col,
                            height=500,
                            width=700
                        )
                        
                        st.plotly_chart(fig)
                    else:
                        st.warning("Could not determine suitable columns or chart type for visualization.")
                else:
                    st.warning("No numeric columns available for chart generation.")
            else:
                st.warning("No data available for visualization.")
