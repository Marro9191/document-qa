import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Add sidebar with menu item
st.sidebar.title("Navigation")
menu = st.sidebar.radio("Menu", ["Insight Conversation"])

# Show title and description
if menu == "Insight Conversation":
    st.title("📄 Comcore Prototype v1")
    st.write(
        "Upload CSV file below and ask analytical questions. "
        "Supported formats: .csv, "
        "and you can also visualize the data with customizable charts. "
        "Please note it has to be UTF-8 encoded."
    )

    # Get OpenAI API key from Streamlit secrets
    try:
        openai_api_key = st.secrets["openai"]["api_key"]
        client = OpenAI(api_key=openai_api_key)
    except KeyError:
        st.error("Please add your OpenAI API key to `.streamlit/secrets.toml` under the key `openai.api_key`.")
        st.stop()

    # File uploader
    uploaded_file = st.file_uploader(
        "Upload a document (.csv)",
        type="csv"
    )

    # Question input
    question = st.text_area(
        "Now ask a question about the document!",
        placeholder="Example: What were total number of reviews last month compared to this month for Toothbrush category?",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:
        # Process CSV file
        df = pd.read_csv(uploaded_file)
        document = df.to_string()

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y')

        # Create message for OpenAI
        messages = [
            {
                "role": "user",
                "content": f"Here's a document: {document} \n\n---\n\n {question}",
            }
        ]

        # Check if we should skip the OpenAI response
        show_openai_response = not ("reviews" in question.lower() and 
                                   "last month" in question.lower() and 
                                   "this month" in question.lower() and 
                                   "toothbrush" in question.lower())

        # Generate and display OpenAI response only if not skipping
        if show_openai_response:
            stream = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                stream=True,
            )

            # Display response
            st.subheader("Response")
            st.write_stream(stream)

        # Custom analysis for review comparison query
        if "reviews" in question.lower() and "last month" in question.lower() and "this month" in question.lower():
            current_date = datetime.now()
            current_month = current_date.month
            current_year = current_date.year
            
            # Adjust for if current month is January
            last_month_year = current_year - 1 if current_month == 1 else current_year
            last_month = 12 if current_month == 1 else current_month - 1

            # Filter data based on category if specified
            category = "Toothbrush"  # Corrected from "Tootbrush" to "Toothbrush"
            if category:
                df_filtered = df[df['category'].str.lower() == category.lower()]
            else:
                df_filtered = df

            # Calculate totals
            this_month_data = df_filtered[
                (df_filtered['date'].dt.month == current_month) & 
                (df_filtered['date'].dt.year == current_year)
            ]
            last_month_data = df_filtered[
                (df_filtered['date'].dt.month == last_month) & 
                (df_filtered['date'].dt.year == last_month_year)
            ]

            this_month_reviews = this_month_data['reviews'].sum()
            last_month_reviews = last_month_data['reviews'].sum()

            # Display results (no OpenAI response here)
            st.subheader("Analysis Results")
            st.write(f"Total Reviews This Month: {this_month_reviews}")
            st.write(f"Total Reviews Last Month: {last_month_reviews}")

            # Generate visualization
            st.subheader("Visualization")
            fig = go.Figure(data=[
                go.Bar(
                    x=['Last Month', 'This Month'],
                    y=[last_month_reviews, this_month_reviews],
                    marker_color=['#FF6B6B', '#4ECDC4']
                )
            ])
            
            fig.update_layout(
                title=f"Reviews Comparison - {category if category else 'All Categories'}",
                xaxis_title="Period",
                yaxis_title="Number of Reviews",
                height=500,
                width=700
            )
            
            st.plotly_chart(fig)

        # General visualization options
        st.subheader("Custom Visualization")
        if not df.empty:
            chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter", "Area"])
            x_col = st.selectbox("X-axis", df.columns)
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns
            
            if len(numeric_cols) > 0:
                y_col = st.selectbox("Y-axis", numeric_cols)
                
                color_option = st.selectbox("Color by", ["Single Color"] + df.columns.tolist())
                if color_option == "Single Color":
                    color = st.color_picker("Pick a color", "#00f900")
                else:
                    color = color_option

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
                            marker=dict(color=df[color] if color_option != "Single Color" else color, size=10)
                        ))
                    elif chart_type == "Area":
                        fig.add_trace(go.Scatter(
                            x=df[x_col], 
                            y=df[y_col], 
                            fill='tozeroy',
                            line=dict(color=color if color_option == "Single Color" else None)
                        ))

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
