#!/usr/bin/env python3
"""
GiAs-llm Benchmark Visualizer
==============================

Genera grafici e report HTML dai risultati del benchmark.

Usage:
    python3 visualize_benchmark.py benchmark_results.json
"""

import json
import sys
import argparse
from typing import Dict, List
from datetime import datetime


def generate_html_report(data: Dict, output_file: str = "benchmark_report.html"):
    """Genera report HTML interattivo con grafici"""

    stats = data["statistics"]
    backends = list(stats.keys())

    # Prepara dati per grafici
    accuracy_data = {b: stats[b]["accuracy"] for b in backends}
    time_data = {b: stats[b]["avg_response_time_ms"] for b in backends}

    # Template HTML
    html = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GiAs-llm Backend Comparison Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        header p {{
            opacity: 0.9;
            font-size: 1.1em;
        }}

        .content {{
            padding: 40px;
        }}

        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .stat-card h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }}

        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #333;
        }}

        .stat-card .label {{
            color: #666;
            margin-top: 5px;
        }}

        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }}

        .chart-container {{
            background: #f9fafb;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .chart-container h2 {{
            color: #667eea;
            margin-bottom: 20px;
            text-align: center;
        }}

        .winner-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin-left: 10px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}

        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}

        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
        }}

        tr:hover {{
            background: #f5f7fa;
        }}

        .accuracy-high {{
            color: #11998e;
            font-weight: bold;
        }}

        .accuracy-medium {{
            color: #f39c12;
            font-weight: bold;
        }}

        .accuracy-low {{
            color: #e74c3c;
            font-weight: bold;
        }}

        footer {{
            background: #f9fafb;
            padding: 20px;
            text-align: center;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 GiAs-llm Backend Comparison</h1>
            <p>Performance Analysis: {" vs ".join(b.upper() for b in backends)}</p>
            <p style="font-size: 0.9em; opacity: 0.8;">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </header>

        <div class="content">
            <!-- Summary Cards -->
            <div class="summary">
"""

    # Aggiungi summary cards per ogni backend
    for backend in backends:
        s = stats[backend]
        winner_accuracy = max(backends, key=lambda b: stats[b]["accuracy"]) == backend
        winner_speed = min(backends, key=lambda b: stats[b]["avg_response_time_ms"]) == backend

        html += f"""
                <div class="stat-card">
                    <h3>{backend.upper()}</h3>
                    <div class="value">{s['accuracy']:.1f}%</div>
                    <div class="label">Accuracy {'🏆' if winner_accuracy else ''}</div>
                </div>

                <div class="stat-card">
                    <h3>{backend.upper()} Speed</h3>
                    <div class="value">{s['avg_response_time_ms']:.0f}</div>
                    <div class="label">ms avg {'⚡' if winner_speed else ''}</div>
                </div>
"""

    html += """
            </div>

            <!-- Charts -->
            <div class="charts">
                <div class="chart-container">
                    <h2>📊 Accuracy Comparison</h2>
                    <canvas id="accuracyChart"></canvas>
                </div>

                <div class="chart-container">
                    <h2>⚡ Response Time Comparison</h2>
                    <canvas id="timeChart"></canvas>
                </div>
            </div>

            <!-- Detailed Table -->
            <div class="chart-container">
                <h2>📋 Detailed Statistics</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Backend</th>
                            <th>Total Tests</th>
                            <th>Correct</th>
                            <th>Accuracy</th>
                            <th>Avg Time (ms)</th>
                            <th>Min Time (ms)</th>
                            <th>Max Time (ms)</th>
                            <th>Std Dev</th>
                            <th>Errors</th>
                        </tr>
                    </thead>
                    <tbody>
"""

    for backend in backends:
        s = stats[backend]
        accuracy_class = "accuracy-high" if s['accuracy'] >= 90 else "accuracy-medium" if s['accuracy'] >= 70 else "accuracy-low"

        html += f"""
                        <tr>
                            <td><strong>{backend.upper()}</strong></td>
                            <td>{s['total_tests']}</td>
                            <td>{s['correct']}</td>
                            <td class="{accuracy_class}">{s['accuracy']:.2f}%</td>
                            <td>{s['avg_response_time_ms']:.2f}</td>
                            <td>{s['min_response_time_ms']:.2f}</td>
                            <td>{s['max_response_time_ms']:.2f}</td>
                            <td>{s['std_response_time_ms']:.2f}</td>
                            <td>{s['errors']}</td>
                        </tr>
"""

    html += """
                    </tbody>
                </table>
            </div>
        </div>

        <footer>
            <p>GiAs-llm Backend Comparison Tool | Regione Campania</p>
        </footer>
    </div>

    <script>
        // Accuracy Chart
        const accuracyCtx = document.getElementById('accuracyChart').getContext('2d');
        new Chart(accuracyCtx, {
            type: 'bar',
            data: {
                labels: [""" + ", ".join(f"'{b.upper()}'" for b in backends) + """],
                datasets: [{
                    label: 'Accuracy (%)',
                    data: [""" + ", ".join(str(accuracy_data[b]) for b in backends) + """],
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(17, 153, 142, 0.8)'
                    ],
                    borderColor: [
                        'rgba(102, 126, 234, 1)',
                        'rgba(17, 153, 142, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });

        // Response Time Chart
        const timeCtx = document.getElementById('timeChart').getContext('2d');
        new Chart(timeCtx, {
            type: 'bar',
            data: {
                labels: [""" + ", ".join(f"'{b.upper()}'" for b in backends) + """],
                datasets: [{
                    label: 'Avg Response Time (ms)',
                    data: [""" + ", ".join(str(time_data[b]) for b in backends) + """],
                    backgroundColor: [
                        'rgba(243, 156, 18, 0.8)',
                        'rgba(231, 76, 60, 0.8)'
                    ],
                    borderColor: [
                        'rgba(243, 156, 18, 1)',
                        'rgba(231, 76, 60, 1)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value + ' ms';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    </script>
</body>
</html>
"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ HTML report generated: {output_file}")
    print(f"   Open it in your browser to view interactive charts")


def print_summary(data: Dict):
    """Stampa summary testuale"""
    print("\n" + "=" * 80)
    print(" " * 30 + "BENCHMARK SUMMARY")
    print("=" * 80)

    stats = data["statistics"]

    for backend, s in stats.items():
        print(f"\n{backend.upper()}:")
        print(f"  Accuracy:          {s['accuracy']:.2f}%")
        print(f"  Avg Response Time: {s['avg_response_time_ms']:.2f} ms")
        print(f"  Total Tests:       {s['total_tests']}")
        print(f"  Errors:            {s['errors']}")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Visualize GiAs-llm benchmark results"
    )
    parser.add_argument(
        "input_file",
        help="Input JSON file from compare_llm_backends.py"
    )
    parser.add_argument(
        "--output",
        default="benchmark_report.html",
        help="Output HTML file (default: benchmark_report.html)"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print text summary only (no HTML)"
    )

    args = parser.parse_args()

    # Load data
    try:
        with open(args.input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {args.input_file}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Error: Invalid JSON file: {args.input_file}")
        sys.exit(1)

    # Print summary
    print_summary(data)

    # Generate HTML report
    if not args.summary:
        generate_html_report(data, args.output)


if __name__ == "__main__":
    main()
