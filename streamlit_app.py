import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta

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
        placeholder="Examples: What were total number of reviews last month compared to this month for tootbrush category? Or: Please provide me reviews month over month? Or: Which of our promos drove most sales for last two months?",
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

        # Generate answer using OpenAI
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True,
        )

        # Display response
        st.subheader("Response")
        st.write_stream(stream)

        # Query 1: Last month vs this month comparison
        if "reviews" in question.lower() and "last month" in question.lower() and "this month" in question.lower():
            current_date = datetime.now()
            current_month = current_date.month
            current_year = current_date.year
            
            last_month_year = current_year - 1 if current_month == 1 else current_year
            last_month = 12 if current_month == 1 else current_month - 1

            category = "Tootbrush" if "tootbrush" in question.lower() else None
            if category:
                df_filtered = df[df['category'].str.lower() == category.lower()]
            else:
                df_filtered = df

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

            st.subheader("Analysis Results")
            st.write(f"Total Reviews This Month: {this_month_reviews}")
            st.write(f"Total Reviews Last Month: {last_month_reviews}")

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

        # Query 2: Month over month reviews
        elif "reviews" in question.lower() and "month over month" in question.lower():
            df['month_year'] = df['date'].dt.to_period('M')
            monthly_reviews = df.groupby('month_year')['reviews'].sum().reset_index()
            monthly_reviews['month_year'] = monthly_reviews['month_year'].astype(str)

            st.subheader("Analysis Results")
            st.write("Monthly Reviews:")
            st.dataframe(monthly_reviews)

            st.subheader("Visualization")
            fig = go.Figure(data=[
                go.Scatter(
                    x=monthly_reviews['month_year'],
                    y=monthly_reviews['reviews'],
                    mode='lines+markers',
                    line=dict(color='#4ECDC4', width=2),
                    marker=dict(size=8)
                )
            ])
            
            fig.update_layout(
                title="Reviews Trend Month over Month",
                xaxis_title="Month",
                yaxis_title="Number of Reviews",
                height=500,
                width=700,
                xaxis=dict(tickangle=45)
            )
            
            st.plotly_chart(fig)

        # Query 3: Promos driving most sales for last two months
        elif "promos" in question.lower() and "sales" in question.lower() and "last two months" in question.lower():
            current_date = datetime.now()
            two_months_ago = current_date - relativedelta(months=2)
            
            # Filter for last two months
            df_last_two_months = df[df['date'] >= two_months_ago]
            df_last_two_months['month_year'] = df_last_two_months['date'].dt.to_period('M')
            
            # Group by promo and month
            promo_sales = df_last_two_months.groupby(['promo', 'month_year'])['Sales'].sum().reset_index()
            promo_sales['month_year'] = promo_sales['month_year'].astype(str)
            
            # Get unique months and promos
            months = sorted(promo_sales['month_year'].unique())
            promos = promo_sales['promo'].unique()

            st.subheader("Analysis Results")
            st.write("Sales by Promo for Last Two Months:")
            st.dataframe(promo_sales)

            # Create line chart with scatter points
            st.subheader("Visualization")
            fig = go.Figure()
            
            colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEEAD']  # Add more colors if needed
            
            for i, promo in enumerate(promos):
                promo_data = promo_sales[promo_sales['promo'] == promo]
                fig.add_trace(
                    go.Scatter(
                        x=promo_data['month_year'],
                        y=promo_data['Sales'],
                        mode='lines+markers',
                        name=str(promo),
                        line=dict(color=colors[i % len(colors)], width=2),
                        marker=dict(size=10)
                    )
                )

            fig.update_layout(
                title="Sales by Promo for Last Two Months",
                xaxis_title="Month",
                yaxis_title="Sales",
                height=500,
                width=700,
                xaxis=dict(tickangle=45)
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
