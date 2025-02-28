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
                if "toothbrush" in question.lower() and "reviews" in question.lower():
                    filtered_df = df[df['Category'].str.lower() == 'toothbrush'] if 'Category' in df.columns else df
                    if 'Date' in df.columns:
                        filtered_df['Date'] = pd.to_datetime(filtered_df['Date']).dt.strftime('%Y-%m')
                        filtered_df = filtered_df.groupby('Date')['Reviews'].sum().reset_index()
                
                # Display only relevant data table
                if not filtered_df.empty:
                    st.write("Relevant Data Table (including dates):")
                    st.dataframe(filtered_df)
                else:
                    st.warning("No relevant data found for the query.")

            # Dynamically generate the most relevant graph based on the query
            if not filtered_df.empty:
                numeric_cols = filtered_df.select_dtypes(include=['int64', 'float64']).columns
                if len(numeric_cols) > 0:
                    # Determine the most relevant chart type and data based on the query
                    if "toothbrush" in question.lower() and "reviews" in question.lower() and 'Date' in filtered_df.columns:
                        # Time-series data (e.g., reviews by month) – use Bar or Line chart
                        chart_type = "Bar"  # Default to Bar for time-series, but Line could also work
                        x_col = 'Date'
                        y_col = 'Reviews'
                        title = "Toothbrush Reviews by Month"
                        color = "#00f900"  # Default single color (green, as in your example)

                    elif "performance" in question.lower() and 'Date' in filtered_df.columns:
                        # Example for performance vs. date (like your screenshot) – use Bar chart
                        chart_type = "Bar"
                        x_col = 'Date'
                        y_col = 'Performance' if 'Performance' in numeric_cols else numeric_cols[0]
                        title = "Date vs Performance"
                        color = "#00f900"  # Green, matching your screenshot

                    elif any(keyword in question.lower() for keyword in ["distribution", "percentage", "proportion"]):
                        # Categorical or percentage data – use Pie chart
                        chart_type = "Pie"
                        x_col = filtered_df.columns[0]  # Default to first column for categories
                        y_col = numeric_cols[0]  # Default to first numeric column for values
                        title = f"Distribution of {y_col} by {x_col}"
                        color = None  # Pie chart uses default colors

                    else:
                        # Default to Bar chart for other numeric comparisons
                        chart_type = "Bar"
                        x_col = 'Date' if 'Date' in filtered_df.columns else filtered_df.columns[0]
                        y_col = numeric_cols[0]
                        title = f"{x_col} vs {y_col}"
                        color = "#00f900"  # Default green color

                    # Generate the dynamic chart
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
                    st.warning("No numeric columns available for chart generation.")
            else:
                st.warning("No data available for visualization.")
