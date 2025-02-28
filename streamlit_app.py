import streamlit as st
from openai import OpenAI
import pandas as pd
import plotly.graph_objects as go
import re

# ... (previous code remains the same until the visualization section)

if uploaded_file and question:
    # ... (file processing, OpenAI response, and relevant_df logic remain the same)

    # If it's a data file (CSV/Excel), attempt to show only relevant data
    if df is not None:
        # Try to parse the response and question to filter the DataFrame
        relevant_df = None
        try:
            # ... (parsing and filtering logic for relevant_df remains the same)

            # Display relevant data if available
            if relevant_df is not None and not relevant_df.empty:
                st.subheader("Relevant Data Table")
                st.dataframe(relevant_df)
            else:
                st.warning("No specific data table available for this query. Showing only the response above.")

            # Automatically generate visualizations based on the query and relevant_df
            if not relevant_df.empty:
                st.subheader("Data Visualizations")
                
                # Parse the query to infer visualization fields
                question_lower = question.lower()
                numeric_cols = relevant_df.select_dtypes(include=['int64', 'float64']).columns
                categorical_cols = relevant_df.select_dtypes(include=['object', 'category']).columns

                # Automatically select X-axis (categorical or date/time column preferred)
                x_col = None
                if "date" in relevant_df.columns or "month" in relevant_df.columns:
                    x_col = "date" if "date" in relevant_df.columns else "month"
                elif categorical_cols.any():
                    x_col = categorical_cols[0]  # Default to first categorical column

                # Automatically select Y-axis (numeric column preferred)
                y_col = None
                if numeric_cols.any():
                    y_col = numeric_cols[0]  # Default to first numeric column

                # Automatically select chart type based on query and data
                chart_type = "Bar"  # Default to Bar chart
                if "trend" in question_lower or "over time" in question_lower:
                    chart_type = "Line"
                elif "distribution" in question_lower or "proportion" in question_lower:
                    chart_type = "Pie"
                elif "relationship" in question_lower or "correlation" in question_lower:
                    chart_type = "Scatter"

                # Automatically select color (if applicable)
                color_option = "Single Color"
                color = "#00f900"  # Default green color

                # Chart title based on the question
                chart_title = f"Visualization for: {question}"

                # Generate the chart automatically
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
                        fig.add_trace(go.Scatter(
                            x=relevant_df[x_col], 
                            y=relevant_df[y_col], 
                            mode='markers',
                            marker=dict(color=color, size=10)
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
                    st.warning("No suitable columns found for automatic visualization. Please manually select fields below.")

                # Optionally, allow manual overrides with selectboxes for user flexibility
                st.write("Or customize the visualization manually:")
                manual_chart_type = st.selectbox("Chart Type", ["Bar", "Line", "Pie", "Scatter", "Area"], index=["Bar", "Line", "Pie", "Scatter", "Area"].index(chart_type))
                manual_x_col = st.selectbox("X-axis", relevant_df.columns, index=relevant_df.columns.get_loc(x_col) if x_col else 0)
                manual_numeric_cols = relevant_df.select_dtypes(include=['int64', 'float64']).columns
                manual_y_col = st.selectbox("Y-axis", manual_numeric_cols, index=manual_numeric_cols.get_loc(y_col) if y_col and y_col in manual_numeric_cols else 0)
                
                # Color options for manual customization
                manual_color_option = st.selectbox("Color by", ["Single Color"] + relevant_df.columns.tolist(), index=0 if color_option == "Single Color" else relevant_df.columns.get_loc(color_option) + 1)
                if manual_color_option == "Single Color":
                    manual_color = st.color_picker("Pick a color", "#00f900")
                else:
                    manual_color = manual_color_option

                # Chart title for manual customization
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
                        fig.add_trace(go.Scatter(
                            x=relevant_df[manual_x_col], 
                            y=relevant_df[manual_y_col], 
                            mode='markers',
                            marker=dict(
                                color=relevant_df[manual_color] if manual_color_option != "Single Color" else manual_color,
                                size=10
                            )
                        ))
                    
                    elif manual_chart_type == "Area":
                        fig.add_trace(go.Scatter(
                            x=relevant_df[manual_x_col], 
                            y=relevant_df[manual_y_col], 
                            fill='tozeroy',
                            line=dict(color=manual_color if manual_color_option == "Single Color" else None)
                        ))

                    # Update layout
                    fig.update_layout(
                        title=manual_chart_title,
                        xaxis_title=manual_x_col,
                        yaxis_title=manual_y_col,
                        height=500,
                        width=700
                    )
                    
                    st.plotly_chart(fig)
            else:
                st.warning("The uploaded data is empty.")

        # ... (rest of the code remains the same)
