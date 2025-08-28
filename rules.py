# rules.py: Logic for Impact and Improvements in water treatment dashboard
import numpy as np
import pandas as pd
from scipy.stats import linregress  # For trend slope

# Define ideal ranges and factors (based on industrial cooling/heating standards)
METRIC_RULES = {
    'ph': {
        'ideal_min': 7.5,
        'ideal_max': 9.0,
        'impact_factor': 0.15,  # e.g., 15% cost increase per 10% out-of-range due to scaling/corrosion
        'base_cost': 10000,  # Annual base budget assumption; customize per facility
        'high_impact': 'High pH promotes scaling, increasing energy costs by up to 20% and maintenance for cleaning.',
        'low_impact': 'Low pH causes corrosion, leading to equipment damage and repair costs up to $5,000/year.',
        'high_suggestion': 'Add acid (e.g., sulfuric) to lower pH; increase blowdown if alkalinity is high.',
        'low_suggestion': 'Add alkaline (e.g., sodium hydroxide) to raise pH; check for acid leaks.'
    },
    'conductivity': {
        'ideal_min': 0,
        'ideal_max': 1500,  # µS/cm
        'impact_factor': 0.20,
        'base_cost': 10000,
        'high_impact': 'High conductivity indicates TDS buildup, causing fouling and 10-25% higher energy use.',
        'low_impact': 'Low conductivity is generally good but may indicate over-blowdown, wasting water (up to 15% higher usage costs).',
        'high_suggestion': 'Increase blowdown or use reverse osmosis to reduce TDS; monitor cycles of concentration.',
        'low_suggestion': 'Reduce blowdown to conserve water; ensure makeup water quality.'
    },
    'hardness': {
        'ideal_min': 0,
        'ideal_max': 100,  # mg/L CaCO3
        'impact_factor': 0.25,
        'base_cost': 10000,
        'high_impact': 'High hardness causes scaling, reducing heat transfer efficiency and adding 20-30% to energy bills.',
        'low_impact': 'Low hardness is ideal, but if too low, it may increase corrosion risk (5-10% higher inhibitor costs).',
        'high_suggestion': 'Install water softeners or use scale inhibitors (e.g., phosphonates); perform regular descaling.',
        'low_suggestion': 'Monitor corrosion inhibitors; adjust if pH is low.'
    },
    'p_alkalinity': {
        'ideal_min': 100,
        'ideal_max': 300,  # mg/L CaCO3
        'impact_factor': 0.18,
        'base_cost': 10000,
        'high_impact': 'High P-alkalinity promotes scaling in alkaline conditions, increasing cleaning costs.',
        'low_impact': 'Low P-alkalinity reduces buffering, leading to pH swings and corrosion (10-20% higher repair costs).',
        'high_suggestion': 'Acid feed to reduce alkalinity; optimize blowdown.',
        'low_suggestion': 'Add bicarbonate if needed; stabilize pH control.'
    },
    # Add similar rules for other metrics like m_alkalinity, chloride, calcium, temperature, no2, po4, so2, mo, live_atp, free_chlorine, total_chlorine, max_temperature
    # Example for no2 (nitrite inhibitor):
    'no2': {
        'ideal_min': 200,
        'ideal_max': 600,  # mg/L
        'impact_factor': 0.12,
        'base_cost': 10000,
        'high_impact': 'High NO2 may indicate over-dosing, wasting chemicals (5-10% higher treatment costs).',
        'low_impact': 'Low NO2 allows corrosion in closed systems, leading to leaks and downtime costs.',
        'high_suggestion': 'Reduce inhibitor dosing; monitor for overfeed.',
        'low_suggestion': 'Increase nitrite-based inhibitor; check for oxygen ingress.'
    },
    # ... (extend for all metrics in numeric_columns)
}


def analyze_metric(df, metric):
    if len(df) < 2 or metric not in METRIC_RULES:
        return {
            'impact': 'Not enough data or metric not supported for impact assessment.',
            'improvements': 'Not enough data or metric not supported for improvement suggestions.'
        }

    rules = METRIC_RULES[metric]
    avg_value = df[metric].mean()
    out_of_range_pct = ((df[metric] < rules['ideal_min']) | (df[metric] > rules['ideal_max'])).mean() * 100

    # Trend: Use linear regression slope
    x = np.arange(len(df))
    slope, _, _, _, _ = linregress(x, df[metric])
    trend = 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'

    # Impact: Estimate cost based on out-of-range % and factor
    estimated_cost_impact = out_of_range_pct / 100 * rules['impact_factor'] * rules['base_cost']
    impact_text = f'The average {metric} is {avg_value:.2f} ({out_of_range_pct:.1f}% out of ideal range {rules["ideal_min"]}-{rules["ideal_max"]}). '
    impact_text += f'Trend is {trend}. Estimated annual budget impact: +${estimated_cost_impact:.0f} due to '
    impact_text += rules['high_impact'] if avg_value > rules['ideal_max'] else rules['low_impact']

    # Improvements: Based on average vs. range
    improvements_text = f'To optimize {metric}: '
    improvements_text += rules['high_suggestion'] if avg_value > rules['ideal_max'] else rules['low_suggestion']
    improvements_text += ' Consult a water treatment specialist for site-specific adjustments.'

    return {'impact': impact_text, 'improvements': improvements_text}