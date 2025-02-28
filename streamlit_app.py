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
            if "toothbrush" in question.lower() and "reviews" in question.lower():
                filtered_df = df[df['Category'].str.lower() == 'toothbrush'] if 'Category' in df.columns else df
                if 'Date' in df.columns:
                    filtered_df['Date'] = pd.to_datetime(filtered_df['Date']).dt.strftime('%Y-%m')
                    filtered_df = filtered_df.groupby('Date')['Reviews'].sum().reset_index()
            
            # Display the relevant data table
            st.write("Relevant Data Table (including dates):")
            st.dataframe(filtered_df)

            # Visualization options (auto-select defaults but keep all options)
            if not filtered_df.empty:
                st.write("Generate a chart:")
                # Auto-select defaults
                default_chart_type = "Bar"
                default_x_col = filtered_df.columns[0] if 'Date' in filtered_df.columns else filtered_df.columns[0]
                numeric_cols = filtered_df.select_dtypes(include=['int64', 'float64']).columns
                default_y_col = numeric_cols[0] if len(numeric_cols) > 0 else None
                default_color = "Single Color"

                chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter", "Area"], index=["Bar", "Line", "Pie", "Scatter", "Area"].index(default_chart_type))
                x_col = st.selectbox("X-axis", filtered_df.columns, index=filtered_df.columns.get_loc(default_x_col) if default_x_col in filtered_df.columns else 0)
                
                if len(numeric_cols) > 0:
                    y_col = st.selectbox("Y-axis", numeric_cols, index=numeric_cols.get_loc(default_y_col) if default_y_col in numeric_cols else 0)
                    
                    # Color options (auto-select "Single Color")
                    color_option = st.selectbox("Color by", ["Single Color"] + filtered_df.columns.tolist(), index=0)
                    if color_option == "Single Color":
                        color = st.color_picker("Pick a color", "#00f900")
                    else:
                        color = color_option

                    # Chart customization (auto-suggested title)
                    suggested_title = f"{filtered_df.columns[0]} vs {y_col}" if 'Date' in filtered_df.columns else "Data Visualization"
                    chart_title = st.text_input("Chart Title", suggested_title)
                    
                    if st.button("Generate Chart"):
                        fig = go.Figure()
                        
                        if chart_type == "Bar":
                            fig.add_trace(go.Bar(x=filtered_df[x_col], y=filtered_df[y_col], marker_color=color if color_option == "Single Color" else None))
                        
                        elif chart_type == "Line":
                            fig.add_trace(go.Scatter(x=filtered_df[x_col], y=filtered_df[y_col], mode='lines', line=dict(color=color if color_option == "Single Color" else None)))
                        
                        elif chart_type == "Pie":
                            pie_data = filtered_df.groupby(x_col)[y_col].sum()
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

                        # Update layout with labeled axes
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
                st.warning("The filtered data is empty.")
