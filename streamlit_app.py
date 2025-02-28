import streamlit as st

# File uploader (this should be at the top of your app or before any use of uploaded_file)
uploaded_file = st.file_uploader(
    "Upload a document (.txt, .md, .csv, .xlsx)",
    type=("txt", "md", "csv", "xlsx")
)

# Check if uploaded_file is None and handle it explicitly
is_file_uploaded = uploaded_file is not None

# Use columns for text area and send button
col1, col2 = st.columns([0.9, 0.1])  # 90% for text area, 10% for button

with col1:
    question = st.text_area(
        "Now ask a question about the document!",
        placeholder="For example: What were total number of reviews last month compared to this month for toothbrush category? Give me total for each month only.(Please note it has to be UTF 8 encoded)",
        key="question_input",
        disabled=not is_file_uploaded,  # Use the boolean variable for clarity
    )

with col2:
    send_button = st.button(
        "Send",
        key="send_button",
        disabled=not is_file_uploaded or not question.strip(),  # Disable if no file or empty question
        help="Send your question about the document"
    )

# Process only if the send button is clicked and conditions are met
if send_button and is_file_uploaded and question:
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

    # Display the response
    st.subheader("Response")
    st.write_stream(stream)

    # If it's a data file (CSV/Excel), offer visualization options
    if df is not None:
        st.subheader("Data Visualizations")
        
        # Display the table
        st.write("Data Table:")
        st.dataframe(df)

        # Visualization options (rest of your code remains the same)
        if not df.empty:
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
