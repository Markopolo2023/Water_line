# app.py (Dash dashboard app)
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import sqlite3
import os

# Path to the SQLite database
DB_PATH = os.path.join('data_processing', 'hand.db')


# Function to load data from SQLite
def load_data():
    if not os.path.exists(DB_PATH):
        print("Database not found at:", DB_PATH)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        reports_df = pd.read_sql_query("SELECT * FROM hand", conn)
        print("reports_df columns:", reports_df.columns.tolist())
    except Exception as e:
        print("Error loading hand:", e)
        reports_df = pd.DataFrame()

    try:
        systems_df = pd.read_sql_query("SELECT * FROM systems", conn)
        print("systems_df columns:", systems_df.columns.tolist())
    except Exception as e:
        print("Error loading systems:", e)
        systems_df = pd.DataFrame()

    # Merge hand and systems
    full_df = systems_df.merge(reports_df, left_on='report_id', right_on='id', suffixes=('_system', '_report'),
                               how='left')
    print("full_df columns:", full_df.columns.tolist())
    conn.close()
    return reports_df, systems_df, full_df


# Load initial data
reports_df, systems_df, full_df = load_data()

# Initialize Dash app with a modern, futuristic theme
app = dash.Dash(__name__)

# Custom CSS for futuristic, simple, modern look
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
                background-color: #0a0a0a;
                color: #e0e0e0;
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 20px;
            }
            .dashboard-container {
                max-width: 1200px;
                margin: auto;
            }
            h1, h2, h3 {
                color: #00ffcc;
                text-shadow: 0 0 5px #00ffcc;
            }
            .card {
                background-color: #1a1a1a;
                border: 1px solid #00ffcc;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 0 10px rgba(0, 255, 204, 0.3);
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

# Identify numeric columns for metrics from systems table
numeric_columns = ['cond', 'ph', 'temp', 'p_alk', 'm_alk', 'chloride', 'hardness',
                   'calcium', 'po4', 'so3', 'mo', 'no2', 'live_atp', 'free_chlorine',
                   'total_chlorine', 'max_temp']
metric_options = [col for col in numeric_columns if col in full_df.columns]

# Dashboard layout
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
                html.H3(f"{len(reports_df['facility'].unique()) if not reports_df.empty else 0}"),
                html.P('Unique Facilities')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'}),
            html.Div([
                html.H3(f"{len(reports_df['chemist'].dropna().unique()) if not reports_df.empty else 0}"),
                html.P('Chemists')
            ], style={'textAlign': 'center', 'width': '33%', 'display': 'inline-block'})
        ])
    ]),

    # Section 2: Metrics Visualization with selections
    html.Div(className='card', children=[
        html.H2('Metrics Analysis'),
        dcc.Dropdown(
            id='facility-dropdown',
            options=[{'label': f, 'value': f} for f in sorted(full_df['facility'].unique()) if not full_df.empty],
            placeholder="Select a Facility"
        ),
        dcc.Dropdown(
            id='system-dropdown',
            options=[],
            placeholder="Select a System"
        ),
        dcc.Dropdown(
            id='metric-dropdown',
            options=[{'label': col, 'value': col} for col in metric_options],
            value='cond' if 'cond' in metric_options else None,
            placeholder="Select a Metric"
        ),
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


# Callback to update system dropdown based on facility selection
@app.callback(
    Output('system-dropdown', 'options'),
    Input('facility-dropdown', 'value')
)
def update_system_dropdown(selected_facility):
    if selected_facility is None or full_df.empty:
        return []
    systems = full_df[full_df['facility'] == selected_facility]['system_name'].unique()
    return [{'label': s, 'value': s} for s in sorted(systems)]


# Callback for updating the metric chart, impact, and improvements
@app.callback(
    [
        Output('metric-chart', 'figure'),
        Output('impact', 'children'),
        Output('improvements', 'children')
    ],
    [
        Input('facility-dropdown', 'value'),
        Input('system-dropdown', 'value'),
        Input('metric-dropdown', 'value')
    ]
)
def update_content(selected_facility, selected_system, selected_metric):
    if None in (
    selected_facility, selected_system, selected_metric) or full_df.empty or selected_metric not in full_df.columns:
        return (
            px.line(title='No data available or select facility, system, and metric'),
            [html.P('No data available or select facility, system, and metric to view impact.')],
            [html.P('No data available or select facility, system, and metric to view improvements.')]
        )

    df = full_df[(full_df['facility'] == selected_facility) & (full_df['system_name'] == selected_system)].copy()
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
        title=f'{selected_metric.upper()} Levels Over Time for {selected_system} at {selected_facility}',
        labels={'date': 'Date', selected_metric: selected_metric.upper()},
        template='plotly_dark'
    )
    fig.update_layout(
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#0a0a0a',
        font_color='#e0e0e0',
        title_font_color='#00ffcc'
    )
    fig.update_traces(line_color='#00ffcc', line_width=3)

    # Placeholder logic for impact and improvements
    if len(df) < 2:
        impact_text = 'Not enough data points to assess impact on budget or savings.'
        improvements_text = 'Not enough data points to suggest improvements.'
    else:
        initial = df.iloc[0][selected_metric]
        final = df.iloc[-1][selected_metric]
        delta = final - initial
        if delta > 0:
            trend = 'increased'
        elif delta < 0:
            trend = 'decreased'
        else:
            trend = 'remained the same'
        impact_text = f'The {selected_metric} level has {trend} from {initial:.2f} to {final:.2f}, potentially impacting the budget. (Add calculations for savings/loss here.)'
        improvements_text = f'To improve the {selected_metric} values, consider adjustments based on the trend. (Add specific suggestions here.)'

    return (
        fig,
        [html.P(impact_text)],
        [html.P(improvements_text)]
    )


if __name__ == '__main__':
    app.run(debug=True)