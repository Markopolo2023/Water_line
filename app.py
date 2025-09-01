# app.py (Dash dashboard app with updated UIUC Blue header color)
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import sqlite3
import os
from datetime import datetime
from rules import analyze_metric  # Import rules.py for Impact/Improvements logic

# Path to the SQLite database
DB_PATH = os.path.join('../Water_line/mssql_export', 'combined.db')


# Function to load data from SQLite
def load_data():
    if not os.path.exists(DB_PATH):
        print("Database not found at:", DB_PATH)
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        # Query the 'data' table
        data_df = pd.read_sql_query("SELECT * FROM data", conn)
        # Convert date column to datetime
        if not data_df.empty and 'date' in data_df.columns:
            data_df['date'] = pd.to_datetime(data_df['date'], errors='coerce')
        print("data_df columns:", data_df.columns.tolist())
    except Exception as e:
        print("Error loading data:", e)
        data_df = pd.DataFrame()
    conn.close()
    return data_df


# Load initial data
full_df = load_data()

# Initialize Dash app
app = dash.Dash(__name__)

# Custom CSS with updated UIUC Blue header color
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
                background-color: #000000; /* Black background */
                color: #FFFFFF; /* White text for readability */
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 20px;
            }
            .dashboard-container {
                max-width: 1200px;
                margin: auto;
            }
            h1, h2, h3 {
                background-color: #000000; /* Black background for headers */
                color: #1E4D8C; /* Lighter UIUC Blue text for better contrast */
                padding: 10px;
                border-radius: 5px;
                text-shadow: 0 0 3px rgba(232, 74, 39, 0.3); /* Subtle orange glow */
            }
            .card {
                background-color: #000000; /* Black background for sections */
                border: 1px solid #E84A27; /* UIUC Orange border */
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 0 8px rgba(232, 74, 39, 0.4); /* Modern orange glow */
            }
            .plotly-graph {
                border: 1px solid #E84A27; /* UIUC Orange border */
                border-radius: 8px;
                box-shadow: 0 0 8px rgba(232, 74, 39, 0.4); /* Modern orange glow */
            }
            .Select-control {
                background-color: #333333 !important; /* Dark grey for dropdown */
                border: 1px solid #E84A27 !important; /* UIUC Orange border */
                color: #FFFFFF !important; /* White text */
            }
            .Select-menu-outer {
                background-color: #333333 !important; /* Dark grey for dropdown options */
                border: 1px solid #E84A27 !important; /* UIUC Orange border */
            }
            .Select-value-label, .Select-placeholder {
                color: #FFFFFF !important; /* White text for visibility */
            }
            .Select-option {
                background-color: #333333 !important; /* Dark grey for options */
                color: #FFFFFF !important; /* White text */
            }
            .Select-option:hover {
                background-color: #4A4A4A !important; /* Lighter grey on hover */
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

# Identify numeric columns for metrics from data table
numeric_columns = [
    'conductivity', 'ph', 'temperature', 'p_alkalinity', 'm_alkalinity', 'chloride',
    'hardness', 'calcium', 'po4', 'so2', 'mo', 'no2', 'live_atp', 'free_chlorine',
    'total_chlorine', 'max_temperature'
]
metric_options = [col for col in numeric_columns if col in full_df.columns]

# Dashboard layout
app.layout = html.Div(className='dashboard-container', children=[
    html.H1('Water Treatment Dashboard', style={'textAlign': 'center'}),

    # Section 1: Overview Cards
    html.Div(className='card', children=[
        html.H2('Overview'),
        html.Div([
            html.Div([
                html.H3(f"{len(full_df)}"),
                html.P('Total Records')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'}),
            html.Div([
                html.H3(f"{len(full_df['facility_name'].unique()) if not full_df.empty else 0}"),
                html.P('Unique Facilities')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'}),
            html.Div([
                html.H3(f"{len(full_df['chemist'].dropna().unique()) if not full_df.empty else 0}"),
                html.P('Chemists')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'})
        ])
    ]),

    # Section 2: Metrics Visualization with selections
    html.Div(className='card', children=[
        html.H2('Metrics Analysis'),
        dcc.Dropdown(
            id='facility-dropdown',
            options=[{'label': f, 'value': f} for f in sorted(full_df['facility_name'].unique()) if not full_df.empty],
            placeholder="Select a Facility"
        ),
        dcc.Dropdown(
            id='system-type-dropdown',
            options=[],
            placeholder="Select a System Type"
        ),
        dcc.Dropdown(
            id='system-dropdown',
            options=[],
            placeholder="Select a System"
        ),
        dcc.Dropdown(
            id='metric-dropdown',
            options=[{'label': col, 'value': col} for col in metric_options],
            value='conductivity' if 'conductivity' in metric_options else None,
            placeholder="Select a Parameter"
        ),
        dcc.Dropdown(
            id='date-range-dropdown',
            options=[
                {'label': 'All Points', 'value': 'all'},
                {'label': 'Custom Date Range', 'value': 'custom'}
            ],
            value='all',
            placeholder="Select Date Range"
        ),
        html.Div(id='date-picker-container', style={'display': 'none'}, children=[
            dcc.DatePickerRange(
                id='date-picker-range',
                min_date_allowed=full_df['date'].min() if not full_df.empty else None,
                max_date_allowed=full_df['date'].max() if not full_df.empty else None,
                start_date=full_df['date'].min() if not full_df.empty else None,
                end_date=full_df['date'].max() if not full_df.empty else None
            )
        ]),
        dcc.Graph(id='metric-chart')
    ]),

    # Section 3: Impact
    html.Div(className='card', children=[
        html.H2('Impact'),
        html.Div(id='impact')
    ]),

    # Section 4: Improvements
    html.Div(className='card', children=[
        html.H2('Improvements'),
        html.Div(id='improvements')
    ])
])


# Callback to update system type dropdown based on facility selection
@app.callback(
    Output('system-type-dropdown', 'options'),
    Input('facility-dropdown', 'value')
)
def update_system_type_dropdown(selected_facility):
    if selected_facility is None or full_df.empty:
        return []
    system_types = full_df[full_df['facility_name'] == selected_facility]['system_type'].dropna().unique()
    return [{'label': s, 'value': s} for s in sorted(system_types)]


# Callback to update system dropdown based on facility and system type selection
@app.callback(
    Output('system-dropdown', 'options'),
    [
        Input('facility-dropdown', 'value'),
        Input('system-type-dropdown', 'value')
    ]
)
def update_system_dropdown(selected_facility, selected_system_type):
    if selected_facility is None or selected_system_type is None or full_df.empty:
        return []
    systems = full_df[
        (full_df['facility_name'] == selected_facility) &
        (full_df['system_type'] == selected_system_type)
        ]['system_name'].dropna().unique()
    return [{'label': s, 'value': s} for s in sorted(systems)]


# Callback to show/hide date picker based on date range selection
@app.callback(
    Output('date-picker-container', 'style'),
    Input('date-range-dropdown', 'value')
)
def toggle_date_picker(date_range):
    if date_range == 'custom':
        return {'display': 'block'}
    return {'display': 'none'}


# Callback for updating the metric chart, impact, and improvements
@app.callback(
    [
        Output('metric-chart', 'figure'),
        Output('impact', 'children'),
        Output('improvements', 'children')
    ],
    [
        Input('facility-dropdown', 'value'),
        Input('system-type-dropdown', 'value'),
        Input('system-dropdown', 'value'),
        Input('metric-dropdown', 'value'),
        Input('date-range-dropdown', 'value'),
        Input('date-picker-range', 'start_date'),
        Input('date-picker-range', 'end_date')
    ]
)
def update_content(selected_facility, selected_system_type, selected_system, selected_metric, date_range, start_date,
                   end_date):
    if None in (selected_facility, selected_system_type, selected_system,
                selected_metric) or full_df.empty or selected_metric not in full_df.columns:
        return (
            px.line(title='No data available or select facility, system type, system, and parameter'),
            [html.P('No data available or select facility, system type, system, and parameter to view impact.')],
            [html.P('No data available or select facility, system type, system, and parameter to view improvements.')]
        )

    df = full_df[
        (full_df['facility_name'] == selected_facility) &
        (full_df['system_type'] == selected_system_type) &
        (full_df['system_name'] == selected_system)
        ].copy()

    # Apply date range filter if custom is selected
    if date_range == 'custom' and start_date and end_date:
        start_date = pd.to_datetime(start_date)
        end_date = pd.to_datetime(end_date)
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

    df[selected_metric] = pd.to_numeric(df[selected_metric], errors='coerce')
    df = df.dropna(subset=[selected_metric]).sort_values('date')

    if len(df) == 0:
        return (
            px.line(title='No data available'),
            [html.P('No data available for impact assessment.')],
            [html.P('No data available for improvement suggestions.')]
        )

    # Create line chart for value over time
    fig = px.line(
        df,
        x='date',
        y=selected_metric,
        title=f'{selected_metric.upper()} Levels Over Time for {selected_system} ({selected_system_type}) at {selected_facility}',
        labels={'date': 'Date', selected_metric: selected_metric.upper()},
        template='plotly_dark'
    )
    fig.update_layout(
        plot_bgcolor='#1C3A6E',  # Slightly lighter Illinois Blue for plot background
        paper_bgcolor='#000000',  # Black to match dashboard background
        font_color='#FFFFFF',  # White text for readability
        title_font_color='#E84A27'  # UIUC Orange for title
    )
    fig.update_traces(line_color='#E84A27', line_width=3)  # UIUC Orange for line

    # Impact and improvements using rules.py
    if len(df) < 2:
        impact_text = 'Not enough data points to assess impact on budget or savings.'
        improvements_text = 'Not enough data points to suggest improvements.'
    else:
        analysis = analyze_metric(df, selected_metric)
        impact_text = analysis['impact']
        improvements_text = analysis['improvements']

    return (
        fig,
        [html.P(impact_text)],
        [html.P(improvements_text)]
    )


if __name__ == '__main__':
    app.run(debug=True)