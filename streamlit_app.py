import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
import re
import numpy as np
from datetime import datetime, timedelta

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
        placeholder="For example: What were total number of reviews last month compared to this month for toothbrush category? Please generate pie chart.",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:
        # Process the uploaded file based on its type
        file_extension = uploaded_file.name.split('.')[-1].lower()
        df = None  # DataFrame for Excel/CSV
        
        if file_extension in ['txt', 'md']:
            document = uploaded_file.read().decode()
        
        elif file_extension == 'csv':
            try:
                df = pd.read_csv(uploaded_file, parse_dates=['date'], dayfirst=True)
                # Ensure date is in DD/MM/YYYY format after reading
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce', format='%d/%m/%Y')
            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
                st.stop()
            document = df.to_string()
        
        elif file_extension == 'xlsx':
            try:
                df = pd.read_excel(uploaded_file, parse_dates=['date'], dayfirst=True)
                # Ensure date is in DD/MM/YYYY format after reading
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce', format='%d/%m/%Y')
            except Exception as e:
                st.error(f"Error reading Excel file: {e}")
                st.stop()
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
                # Simple parsing: look for column names or conditions in the query/response
                question_lower = question.lower()
                response_lower = response.lower()
                
                # Extract potential column names from the question (assuming they match df.columns)
                potential_cols = [col for col in df.columns if col.lower() in question_lower]
                
                if potential_cols:
                    # Start with a basic filter based on the question
                    relevant_df = df[potential_cols].copy()
                    
                    # Ensure 'date' or 'month' column exists and is properly formatted in DD/MM/YYYY
                    if "date" in df.columns:
                        # Ensure date is in DD/MM/YYYY format
                        if pd.api.types.is_datetime64_any_dtype(df['date']):
                            relevant_df['date'] = pd.to_datetime(relevant_df['date'], errors='coerce', format='%d/%m/%Y')
                        else:
                            relevant_df['date'] = pd.to_datetime(relevant_df['date'], errors='coerce', format='%d/%m/%Y', dayfirst=True)
                        # Filter for toothbrush category if it exists
                        if "category" in df.columns:
                            relevant_df = relevant_df[relevant_df['category'].str.contains("toothbrush", case=False, na=False)]
                        # Get the last two months dynamically using current date
                        current_date = datetime.now()  # Dynamic current date
                        last_month = current_date.replace(day=1) - timedelta(days=1)
                        last_month = last_month.replace(day=1)
                        this_month = current_date.replace(day=1)
                        # Format dates as DD/MM/YYYY
                        last_month_str = last_month.strftime('%d/%m/%Y')
                        this_month_str = this_month.strftime('%d/%m/%Y')
                        relevant_df = relevant_df[
                            (relevant_df['date'].dt.strftime('%d/%m/%Y') == last_month_str) | 
                            (relevant_df['date'].dt.strftime('%d/%m/%Y') == this_month_str)
                        ]
                        # Aggregate reviews by month (using formatted date)
                        if "reviews" in relevant_df.columns:
                            relevant_df = relevant_df.groupby(relevant_df['date'].dt.strftime('%d/%m/%Y'))['reviews'].sum().reset_index()
                            relevant_df.columns = ['Date', 'Total Reviews']
                        else:
                            st.warning("No 'reviews' column found in the data.")
                    elif "month" in df.columns:
                        # Handle month as a categorical column (e.g., convert to DD/MM/YYYY format)
                        if "category" in df.columns:
                            relevant_df = relevant_df[relevant_df['category'].str.contains("toothbrush", case=False, na=False)]
                        # Get the last two months dynamically (assuming month names or numbers, convert to DD/MM/YYYY)
                        current_month = current_date.month
                        last_month_num = (current_month - 1) % 12 or 12  # Handle January (1) -> December (12)
                        month_names = {1: '01', 2: '02', 3: '03', 4: '04', 5: '05', 6: '06',
                                      7: '07', 8: '08', 9: '09', 10: '10', 11: '11', 12: '12'}
                        last_month_date = f"01/{month_names[last_month_num]}/{current_date.year}"
                        this_month_date = f"01/{month_names[current_month]}/{current_date.year}"
                        relevant_df = relevant_df[
                            relevant_df['month'].isin([last_month_date, this_month_date])
                        ]
                        # Aggregate reviews by month (using formatted date)
                        if "reviews" in relevant_df.columns:
                            relevant_df = relevant_df.groupby('month')['reviews'].sum().reset_index()
                            relevant_df.columns = ['Date', 'Total Reviews']
                        else:
                            st.warning("No 'reviews' column found in the data.")
                    else:
                        st.warning("No 'date' or 'month' column found in the data.")

                # If no relevant data is found, check if the response implies a summary or aggregation
                if relevant_df is None or relevant_df.empty:
                    # Look for numeric summaries in the response (e.g., totals, counts)
                    numbers = re.findall(r'\d+', response)
                    if numbers and potential_cols:
                        # Create a small summary table if possible (e.g., for last and this month in DD/MM/YYYY format)
                        last_month_str = (current_date.replace(day=1) - timedelta(days=1)).replace(day=1).strftime('%d/%m/%Y')
                        this_month_str = current_date.replace(day=1).strftime('%d/%m/%Y')
                        summary_data = {
                            'Date': [last_month_str, this_month_str],
                            'Total Reviews': [int(numbers[0]) if numbers else 0, int(numbers[1]) if len(numbers) > 1 else 0]
                        }
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

            # Automatically generate visualizations based on the query and relevant_df
            if not relevant_df.empty:
                st.subheader("Data Visualizations")
                
                # Parse the query to infer visualization fields and explicit chart type
                question_lower = question.lower()
                numeric_cols = relevant_df.select_dtypes(include=['int64', 'float64']).columns
                categorical_cols = relevant_df.select_dtypes(include=['object', 'category']).columns

                # Automatically select X-axis (categorical or date/time column preferred)
                x_col = 'Date' if 'Date' in relevant_df.columns else None
                if not x_col and categorical_cols.any():
                    x_col = categorical_cols[0]  # Default to first categorical column

                # Automatically select Y-axis (numeric column preferred)
                y_col = 'Total Reviews' if 'Total Reviews' in relevant_df.columns else None
                if not y_col and numeric_cols.any():
                    y_col = numeric_cols[0]  # Default to first numeric column

                # Automatically predict chart types based on query (if no explicit chart is specified)
                predicted_chart_types = []
                if "trend" in question_lower or "over time" in question_lower:
                    predicted_chart_types.append("Line")
                if "distribution" in question_lower or "proportion" in question_lower:
                    predicted_chart_types.append("Pie")
                if "relationship" in question_lower or "correlation" in question_lower:
                    predicted_chart_types.append("Scatter")
                if "comparison" in question_lower or "total" in question_lower or "count" in question_lower:
                    predicted_chart_types.append("Bar")
                if "area" in question_lower or "cumulative" in question_lower:
                    predicted_chart_types.append("Area")
                if "combo" in question_lower or "combined" in question_lower or ("trend" in question_lower and "comparison" in question_lower):
                    predicted_chart_types.append("Combo")

                # Default to Bar if no specific chart types are inferred
                if not predicted_chart_types:
                    predicted_chart_types = ["Bar"]

                # Check for explicit chart type request in the query
                explicit_chart_type = None
                chart_type_patterns = {
                    "pie": "Pie",
                    "bar": "Bar",
                    "line": "Line",
                    "scatter": "Scatter",
                    "area": "Area",
                    "combo": "Combo"
                }
                for pattern, chart_type in chart_type_patterns.items():
                    if f"please generate {pattern} chart" in question_lower or f"generate {pattern} chart" in question_lower:
                        explicit_chart_type = chart_type
                        break

                # Use explicit chart type if specified, otherwise use predicted chart types
                chart_types = [explicit_chart_type] if explicit_chart_type else predicted_chart_types

                # Automatically select color (if applicable)
                color_option = "Single Color"
                color = "#00f900"  # Default green color

                # Automatically summarize the title based on the query
                keywords = []
                if "month" in question_lower or "date" in question_lower:
                    keywords.append("Monthly")
                if "toothbrush" in question_lower and "category" in question_lower:
                    keywords.append("Toothbrush")
                if "reviews" in question_lower or y_col.lower() in question_lower:
                    keywords.append("Reviews")
                if x_col and x_col.lower() in question_lower:
                    keywords.append(x_col.capitalize())

                # Create a concise title
                chart_title = " ".join(keywords) if keywords else f"Visualization for: {question[:30]}..."  # Limit to 30 chars if no keywords

                # Generate charts automatically for the selected chart type(s)
                for chart_type in chart_types:
                    if x_col and y_col:
                        fig = go.Figure()
                        
                        if chart_type == "Bar":
                            fig.add_trace(go.Bar(x=relevant_df[x_col], y=relevant_df[y_col], marker_color=color))
                        
                        elif chart_type == "Line":
                            fig.add_trace(go.Scatter(x=relevant_df[x_col], y=relevant_df[y_col], mode='lines', line=dict(color=color)))
                        
                        elif chart_type == "Pie":
                            pie_data = relevant_df.groupby(x_col)[y_col].sum()
                            fig.add_trace(go.Pie(labels=pie_data.index, values=pie_data.values))
                        
                        elif chart_type == "Scatter":
                            # Add scatter plot
                            fig.add_trace(go.Scatter(
                                x=relevant_df[x_col], 
                                y=relevant_df[y_col], 
                                mode='markers',
                                marker=dict(color=color, size=10),
                                name='Data Points'
                            ))
                            # Add trend line (linear regression)
                            x = np.array(relevant_df[x_col].astype(float) if pd.api.types.is_numeric_dtype(relevant_df[x_col]) else range(len(relevant_df)))
                            y = np.array(relevant_df[y_col].astype(float))
                            coefficients = np.polyfit(x, y, 1)  # Linear regression (degree 1)
                            trend_line = np.polyval(coefficients, x)
                            fig.add_trace(go.Scatter(
                                x=x if pd.api.types.is_numeric_dtype(relevant_df[x_col]) else relevant_df[x_col],
                                y=trend_line,
                                mode='lines',
                                line=dict(color='red', dash='dash'),
                                name='Trend Line'
                            ))
                        
                        elif chart_type == "Area":
                            fig.add_trace(go.Scatter(
                                x=relevant_df[x_col], 
                                y=relevant_df[y_col], 
                                fill='tozeroy',
                                line=dict(color=color)
                            ))
                        
                        elif chart_type == "Combo":
                            # Combo chart: Combine Bar and Line (e.g., bars for one metric, line for trend)
                            fig.add_trace(go.Bar(x=relevant_df[x_col], y=relevant_df[y_col], name='Bar Data', marker_color=color))
                            fig.add_trace(go.Scatter(x=relevant_df[x_col], y=relevant_df[y_col], mode='lines', name='Line Trend', line=dict(color='red')))

                        # Update layout with DD/MM/YYYY format for dates on X-axis
                        fig.update_layout(
                            title=f"{chart_title} ({chart_type})",
                            xaxis_title=x_col,
                            yaxis_title=y_col,
                            xaxis=dict(
                                tickformat='%d/%m/%Y',  # Format X-axis ticks as DD/MM/YYYY
                                type='category' if not pd.api.types.is_numeric_dtype(relevant_df[x_col]) else 'linear'
                            ),
                            height=500,
                            width=700,
                            showlegend=True  # Show legend for combo and scatter with trend line
                        )
                        
                        st.plotly_chart(fig)
                    else:
                        st.warning(f"No suitable columns found for {chart_type} visualization. Please manually select fields below.")
                        break  # Stop if no suitable columns are found

                # Customize the visualization manually, using all options from the original DataFrame (df)
                st.write("Or customize the visualization manually:")
                manual_chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter", "Area", "Combo"], index=["Bar", "Line", "Pie", "Scatter", "Area", "Combo"].index(chart_types[0]) if chart_types else 0)
                manual_x_col = st.selectbox("X-axis", df.columns, index=df.columns.get_loc(x_col) if x_col and x_col in df.columns else 0)
                manual_numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
                manual_y_col = st.selectbox("Y-axis", manual_numeric_cols, index=manual_numeric_cols.get_loc(y_col) if y_col and y_col in manual_numeric_cols else 0)
                
                # Add option for trend line in manual customization
                show_trend_line = st.checkbox("Show Trend Line", value=False, disabled=manual_chart_type != "Scatter")
                
                # Color options for manual customization, using all columns from df
                manual_color_option = st.selectbox("Color by", ["Single Color"] + df.columns.tolist(), index=0 if color_option == "Single Color" else (df.columns.get_loc(color_option) + 1 if color_option in df.columns else 0))
                if manual_color_option == "Single Color":
                    manual_color = st.color_picker("Pick a color", "#00f900")
                else:
                    manual_color = manual_color_option

                # Chart title for manual customization (use the automatic title as default)
                manual_chart_title = st.text_input("Chart Title", chart_title)
                
                if st.button("Generate Custom Chart"):
                    fig = go.Figure()
                    
                    if manual_chart_type == "Bar":
                        fig.add_trace(go.Bar(x=relevant_df[manual_x_col], y=relevant_df[manual_y_col], marker_color=manual_color if manual_color_option == "Single Color" else None))
                    
                    elif manual_chart_type == "Line":
                        fig.add_trace(go.Scatter(x=relevant_df[manual_x_col], y=relevant_df[manual_y_col], mode='lines', line=dict(color=manual_color if manual_color_option == "Single Color" else None)))
                    
                    elif manual_chart_type == "Pie":
                        pie_data = relevant_df.groupby(manual_x_col)[manual_y_col].sum()
                        fig.add_trace(go.Pie(labels=pie_data.index, values=pie_data.values))
                    
                    elif manual_chart_type == "Scatter":
                        # Add scatter plot
                        fig.add_trace(go.Scatter(
                            x=relevant_df[manual_x_col], 
                            y=relevant_df[manual_y_col], 
                            mode='markers',
                            marker=dict(color=manual_color if manual_color_option == "Single Color" else relevant_df[manual_color], size=10),
                            name='Data Points'
                        ))
                        # Add trend line if selected
                        if show_trend_line:
                            x = np.array(relevant_df[manual_x_col].astype(float) if pd.api.types.is_numeric_dtype(relevant_df[manual_x_col]) else range(len(relevant_df)))
                            y = np.array(relevant_df[manual_y_col].astype(float))
                            coefficients = np.polyfit(x, y, 1)  # Linear regression (degree 1)
                            trend_line = np.polyval(coefficients, x)
                            fig.add_trace(go.Scatter(
                                x=x if pd.api.types.is_numeric_dtype(relevant_df[manual_x_col]) else relevant_df[manual_x_col],
                                y=trend_line,
                                mode='lines',
                                line=dict(color='red', dash='dash'),
                                name='Trend Line'
                            ))
                    
                    elif manual_chart_type == "Area":
                        fig.add_trace(go.Scatter(
                            x=relevant_df[manual_x_col], 
                            y=relevant_df[manual_y_col], 
                            fill='tozeroy',
                            line=dict(color=manual_color if manual_color_option == "Single Color" else None)
                        ))
                    
                    elif manual_chart_type == "Combo":
                        # Combo chart: Combine Bar and Line (e.g., bars for one metric, line for trend)
                        fig.add_trace(go.Bar(x=relevant_df[manual_x_col], y=relevant_df[manual_y_col], name='Bar Data', marker_color=manual_color if manual_color_option == "Single Color" else None))
                        fig.add_trace(go.Scatter(x=relevant_df[manual_x_col], y=relevant_df[manual_y_col], mode='lines', name='Line Trend', line=dict(color='red' if manual_color_option == "Single Color" else None)))

                    # Update layout with DD/MM/YYYY format for dates on X-axis
                    fig.update_layout(
                        title=manual_chart_title,
                        xaxis_title=manual_x_col,
                        yaxis_title=manual_y_col,
                        xaxis=dict(
                            tickformat='%d/%m/%Y',  # Format X-axis ticks as DD/MM/YYYY
                            type='category' if not pd.api.types.is_numeric_dtype(relevant_df[manual_x_col]) else 'linear'
                        ),
                        height=500,
                        width=700,
                        showlegend=show_trend_line or manual_chart_type == "Combo"  # Show legend for trend line or combo chart
                    )
                    
                    st.plotly_chart(fig)
            else:
                st.warning("The uploaded data is empty.")
