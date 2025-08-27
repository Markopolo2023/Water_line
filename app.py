# app.py (Dash dashboard app)

import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import sqlite3
import os

# Path to the SQLite database (assuming it's in the project root; adjust if needed)
DB_PATH = 'reports.db'  # Produced by report_processor.py in data_processing


# Function to load data from SQLite
def load_data():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)

    # Load reports
    reports_df = pd.read_sql_query("SELECT * FROM reports", conn)

    # Load systems
    systems_df = pd.read_sql_query("SELECT * FROM systems", conn)

    # Load metrics and pivot for easier visualization (metric_key as columns)
    metrics_df = pd.read_sql_query("SELECT * FROM metrics", conn)
    metrics_pivot = metrics_df.pivot_table(
        index='system_id',
        columns='metric_key',
        values='metric_value',
        aggfunc='first'  # Since values are unique per key
    ).reset_index()

    # Join dataframes for comprehensive views
    systems_with_reports = systems_df.merge(reports_df, left_on='report_id', right_on='id',
                                            suffixes=('_system', '_report'))
    full_df = systems_with_reports.merge(metrics_pivot, left_on='id_system', right_on='system_id')

    conn.close()

    return reports_df, systems_df, full_df


# Load initial data
reports_df, systems_df, full_df = load_data()

# Initialize Dash app with a modern, futuristic theme
app = dash.Dash(__name__)

# Custom CSS for futuristic, simple, modern look (dark background, neon accents, clean fonts)
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Water Treatment Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background-color: #0a0a0a;  /* Dark black background */
                color: #e0e0e0;  /* Light gray text */
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 20px;
            }
            .dashboard-container {
                max-width: 1200px;
                margin: auto;
            }
            h1, h2, h3 {
                color: #00ffcc;  /* Neon cyan for headers */
                text-shadow: 0 0 5px #00ffcc;
            }
            .card {
                background-color: #1a1a1a;  /* Dark gray cards */
                border: 1px solid #00ffcc;  /* Neon border */
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 0 10px rgba(0, 255, 204, 0.3);  /* Glowing shadow */
            }
            .dash-table-container .dash-spreadsheet-container {
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            .dash-table-container th {
                background-color: #333333;
                color: #00ffcc;
            }
            .dash-table-container td {
                border: 1px solid #444444;
            }
            .plotly-graph {
                border: 1px solid #00ffcc;
                border-radius: 8px;
                box-shadow: 0 0 10px rgba(0, 255, 204, 0.3);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Dashboard layout: Simple, sectioned structure
app.layout = html.Div(className='dashboard-container', children=[
    html.H1('Water Treatment Dashboard', style={'textAlign': 'center'}),

    # Section 1: Overview Cards
    html.Div(className='card', children=[
        html.H2('Overview'),
        html.Div([
            html.Div([
                html.H3(f"{len(reports_df)}"),
                html.P('Total Reports')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'}),
            html.Div([
                html.H3(f"{len(reports_df['site_name'].unique())}"),
                html.P('Unique Sites')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'}),
            html.Div([
                html.H3(f"{len(reports_df['technician'].unique())}"),
                html.P('Technicians')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'})
        ])
    ]),

    # Section 2: Reports Table
    html.Div(className='card', children=[
        html.H2('Reports List'),
        dash_table.DataTable(
            id='reports-table',
            columns=[{"name": i, "id": i} for i in reports_df.columns],
            data=reports_df.to_dict('records'),
            style_table={'overflowX': 'auto'},
            page_size=10,
            sort_action="native",
            filter_action="native"
        )
    ]),

    # Section 3: Metrics Visualization
    html.Div(className='card', children=[
        html.H2('Metrics Analysis'),
        dcc.Dropdown(
            id='metric-dropdown',
            options=[{'label': col, 'value': col} for col in full_df.columns if
                     col not in ['id_system', 'report_id', 'id_report', 'system_id', 'comments', 'file_name',
                                 'site_name', 'date', 'technician', 'system_type', 'system_name']],
            value='no2' if 'no2' in full_df.columns else None,  # Default to 'no2' if available
            placeholder="Select a Metric"
        ),
        dcc.Graph(id='metric-chart')
    ]),

    # Section 4: Systems Details
    html.Div(className='card', children=[
        html.H2('Systems Details'),
        dash_table.DataTable(
            id='systems-table',
            columns=[{"name": i, "id": i} for i in systems_df.columns],
            data=systems_df.to_dict('records'),
            style_table={'overflowX': 'auto'},
            page_size=10,
            sort_action="native",
            filter_action="native"
        )
    ])
])


# Callback for updating the metric chart
@app.callback(
    Output('metric-chart', 'figure'),
    Input('metric-dropdown', 'value')
)
def update_chart(selected_metric):
    if selected_metric is None or selected_metric not in full_df.columns:
        return px.bar(title='Select a metric to view')

    # Attempt to convert to numeric for charting (handle non-numeric gracefully)
    full_df[selected_metric] = pd.to_numeric(full_df[selected_metric], errors='coerce')

    fig = px.bar(
        full_df.dropna(subset=[selected_metric]),
        x='date',
        y=selected_metric,
        color='site_name',
        title=f'{selected_metric.upper()} Levels Over Time',
        labels={'date': 'Date', selected_metric: selected_metric.upper()},
        template='plotly_dark'  # Dark theme for futuristic look
    )

    # Customize for futuristic style
    fig.update_layout(
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#0a0a0a',
        font_color='#e0e0e0',
        title_font_color='#00ffcc'
    )
    fig.update_traces(marker_line_color='#00ffcc', marker_line_width=1.5)

    return fig


if __name__ == '__main__':
    app.run_server(debug=True)