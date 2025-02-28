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
            
            # Filter data table based on user query dynamically and perform calculations (addition)
            filtered_df = df.copy()
            show_full_table = "full table" in question.lower() or "all data" in question.lower()
            
            if show_full_table:
                # Show full table if explicitly requested
                st.write("Full Data Table:")
                st.dataframe(df)
            else:
                # Dynamically filter for relevant data types based on query and perform addition (summing)
                keywords = question.lower().split()
                date_col = None
                numeric_col = None
                category_col = None

                # Identify relevant columns (date, numeric, category) based on query
                for col in df.columns:
                    if any(keyword in col.lower() for keyword in keywords):
                        if any(keyword in col.lower() for keyword in ["date", "time"]):
                            date_col = col
                        elif pd.api.types.is_numeric_dtype(df[col]) and any(keyword in col.lower() for keyword in ["number", "count", "total", "value", "review", "reviews"]):
                            numeric_col = col
                        elif 'category' in col.lower():
                            category_col = col

                # Filter for relevant category if mentioned in query
                if 'toothbrush' in question.lower() and category_col and category_col in df.columns:
                    filtered_df = df[df[category_col].str.lower() == 'toothbrush'].copy()
                else:
                    filtered_df = df.copy()

                # Filter data to show only relevant date and numeric columns, performing addition (summing) by month if date exists
                if date_col and numeric_col:
                    if date_col in filtered_df.columns and not filtered_df[date_col].isnull().all():
                        try:
                            filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], format='%d/%m/%y', errors='coerce').dt.strftime('%Y-%m')
                            # Perform addition (summing) of the numeric column by month
                            filtered_df = filtered_df.groupby(date_col)[numeric_col].sum().reset_index()
                            st.write(f"Debug: Summed {numeric_col} by {date_col} for query: {question}")
                        except (ValueError, TypeError) as e:
                            st.warning(f"Could not parse date column '{date_col}' due to: {e}. Trying auto-detection.")
                            filtered_df[date_col] = pd.to_datetime(filtered_df[date_col], errors='coerce').dt.strftime('%Y-%m') if pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]) else filtered_df[date_col]
                            if pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]):
                                filtered_df = filtered_df.groupby(date_col)[numeric_col].sum().reset_index()
                                st.write(f"Debug: Summed {numeric_col} by {date_col} after auto-detection for query: {question}")
                    # Show only date and numeric columns with summed totals
                    filtered_df = filtered_df[[date_col, numeric_col]]
                elif numeric_col:
                    # If no date column, show only the numeric column if relevant, summing if implied by query
                    if any(keyword in question.lower() for keyword in ["total", "sum", "aggregate", "addition"]):
                        filtered_df = pd.DataFrame({numeric_col: [filtered_df[numeric_col].sum()]})
                        st.write(f"Debug: Summed {numeric_col} for query: {question}")
                    else:
                        filtered_df = filtered_df[[numeric_col]]

                # Display only relevant data table if data is filtered, showing summed totals
                if not filtered_df.empty:
                    st.write("Relevant Data Table (including summed dates and numeric data if available):")
                    st.write("Debug: Filtered DataFrame columns:", filtered_df.columns.tolist())  # Debugging output
                    st.dataframe(filtered_df)
                else:
                    st.warning("No relevant data found for the query based on user input.")

            # Dynamically generate the most relevant graph based on user input and file data, performing addition (summing)
            if not filtered_df.empty:
                # Check for numeric columns more thoroughly
                numeric_cols = filtered_df.select_dtypes(include=['int64', 'float64']).columns
                if numeric_cols.empty:
                    # Try to convert columns that might be numeric but stored as strings
                    for col in filtered_df.columns:
                        if filtered_df[col].dtype == 'object' and filtered_df[col].str.match(r'^-?\d*\.?\d+$').all():
                            filtered_df[col] = pd.to_numeric(filtered_df[col], errors='coerce')
                    numeric_cols = filtered_df.select_dtypes(include=['int64', 'float64']).columns

                if len(numeric_cols) > 0:
                    st.write("Debug: Numeric columns found:", numeric_cols.tolist())  # Debugging output
                    # Determine default options for dropdowns based on user query
                    default_chart_type = "Bar"  # Default for comparisons (e.g., last month vs. this month)
                    default_x_col = date_col if date_col and any(keyword in question.lower() for keyword in ["date", "time", "month"]) else filtered_df.columns[0]
                    default_y_col = None
                    default_color = "Single Color"

                    # Prioritize "reviews" or similar for Y-axis if mentioned in query
                    for col in numeric_cols:
                        if 'review' in col.lower() or any(keyword in col.lower() for keyword in question.lower().split()) or \
                           any(keyword in question.lower() for keyword in ["number", "count", "total", "value", "reviews", "sales"]):
                            default_y_col = col
                            break
                    if not default_y_col:
                        default_y_col = numeric_cols[0]  # Last resort: use first numeric column

                    # Visualization options with defaults based on query
                    st.write("Generate a chart:")
                    chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter", "Area"], 
                                            index=["Bar", "Line", "Pie", "Scatter", "Area"].index(default_chart_type))
                    x_col = st.selectbox("X-axis", filtered_df.columns, 
                                        index=filtered_df.columns.get_loc(default_x_col) if default_x_col in filtered_df.columns else 0)
                    
                    if len(numeric_cols) > 0:
                        y_col = st.selectbox("Y-axis", numeric_cols, 
                                            index=numeric_cols.get_loc(default_y_col) if default_y_col in numeric_cols else 0)
                    
                        # Color options (default to "Single Color" with green)
                        color_option = st.selectbox("Color by", ["Single Color"] + filtered_df.columns.tolist(), 
                                                  index=0)  # Default to "Single Color"
                        if color_option == "Single Color":
                            color = st.color_picker("Pick a color", "#00f900")  # Default green color
                        else:
                            color = color_option

                        # Chart customization (auto-suggested title based on query)
                        suggested_title = f"Total {y_col} {'Comparison' if any(keyword in question.lower() for keyword in ['compare', 'comparison', 'vs', 'last month', 'this month']) else 'Trend'} Over {x_col}" if date_col and y_col else "Data Visualization"
                        chart_title = st.text_input("Chart Title", suggested_title)
                    
                        if st.button("Generate Chart"):
                            fig = go.Figure()
                            
                            if chart_type == "Bar":
                                fig.add_trace(go.Bar(x=filtered_df[x_col], y=filtered_df[y_col], marker_color=color if color_option == "Single Color" else None))
                            
                            elif chart_type == "Line":
                                fig.add_trace(go.Scatter(x=filtered_df[x_col], y=filtered_df[y_col], mode='lines', line=dict(color=color if color_option == "Single Color" else None)))
                            
                            elif chart_type == "Pie":
                                pie_data = filtered_df.groupby(x_col)[y_col].sum()  # Ensure summing for Pie chart
                                fig.add_trace(go.Pie(labels=pie_data.index, values=pie_data.values))
                            
                            elif chart_type == "Scatter":
                                fig.add_trace(go.Scatter(
                                    x=filtered_df[x_col], 
                                    y=filtered_df[y_col], 
                                    mode='markers',
                                    marker=dict(
                                        color=filtered_df[color] if color_option != "Single Color" else color,
                                        size=10
                                    )
                                ))
                            
                            elif chart_type == "Area":
                                fig.add_trace(go.Scatter(
                                    x=filtered_df[x_col], 
                                    y=filtered_df[y_col], 
                                    fill='tozeroy',
                                    line=dict(color=color if color_option == "Single Color" else None)
                                ))

                            # Update layout with labeled axes and dynamic title, reflecting summed totals
                            fig.update_layout(
                                title=chart_title,
                                xaxis_title=x_col,
                                yaxis_title=f"Total {y_col}",
                                height=500,
                                width=700
                            )
                            
                            st.plotly_chart(fig)
                    else:
                        st.warning("No numeric columns available for charting.")
                else:
                    st.warning("No numeric columns available for chart generation after attempting conversion.")
            else:
                st.warning("No data available for visualization based on user input.")
