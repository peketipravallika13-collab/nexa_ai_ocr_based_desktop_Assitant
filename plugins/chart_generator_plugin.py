"""
Chart & Graph Generator Plugin for Nexa AI (No API Key Required)
----------------------------------------------------------------
Generates stunning graphs and data visualizations (bar charts, line graphs,
pie charts, scatter plots, histograms, area charts, doughnuts) completely offline
using Matplotlib and saves high-resolution charts locally.
"""

import os
import sys
import json
import logging
import datetime
import subprocess
import webbrowser

logger = logging.getLogger("chart_generator_plugin")

PLUGIN_SCHEMA = {
    "name": "chart_generator",
    "description": "Generate visual graphs and charts (bar, line, pie, doughnut, scatter, histogram, area) from numerical data, save as high-resolution image files, and display them offline.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "chart_type": {
                "type": "STRING",
                "description": "Type of graph: 'bar', 'horizontal_bar', 'line', 'pie', 'doughnut', 'scatter', 'histogram', or 'area'."
            },
            "title": {
                "type": "STRING",
                "description": "Title of the chart (e.g. 'Monthly Revenue 2026', 'User Growth by Region')."
            },
            "data_x": {
                "type": "STRING",
                "description": "X-axis categories or values as a comma-separated list (e.g. 'Jan, Feb, Mar, Apr, May' or '1, 2, 3, 4, 5')."
            },
            "data_y": {
                "type": "STRING",
                "description": "Y-axis numeric values as a comma-separated list (e.g. '12000, 19000, 15000, 28000, 32000')."
            },
            "x_label": {
                "type": "STRING",
                "description": "Optional label for the X-axis (e.g. 'Month', 'Category')."
            },
            "y_label": {
                "type": "STRING",
                "description": "Optional label for the Y-axis (e.g. 'Revenue ($)', 'Count')."
            },
            "color_theme": {
                "type": "STRING",
                "description": "Visual theme: 'modern_dark' (default), 'cyberpunk', 'ocean', 'sunset', 'emerald', or 'minimal_light'."
            },
            "output_filename": {
                "type": "STRING",
                "description": "Optional file path or filename to save the image as (e.g. 'revenue_chart.png')."
            },
            "open_image": {
                "type": "BOOLEAN",
                "description": "Whether to automatically open the generated chart image in the system viewer (default True)."
            }
        },
        "required": ["chart_type", "title", "data_y"]
    }
}

THEME_COLORS = {
    "modern_dark": {
        "bg": "#12131A", "card_bg": "#1C1D26", "text": "#E2E8F0", "grid": "#2D3748",
        "palette": ["#6366F1", "#38BDF8", "#EC4899", "#10B981", "#F59E0B", "#8B5CF6", "#F43F5E"]
    },
    "cyberpunk": {
        "bg": "#0D0B18", "card_bg": "#161329", "text": "#F1F5F9", "grid": "#3B2D60",
        "palette": ["#00F0FF", "#FF007F", "#FFE600", "#7B2CBF", "#00FF66", "#FF5400"]
    },
    "ocean": {
        "bg": "#0B192C", "card_bg": "#1E3E62", "text": "#F1F5F9", "grid": "#295F98",
        "palette": ["#00ADB5", "#38BDF8", "#0284C7", "#818CF8", "#34D399", "#67E8F9"]
    },
    "sunset": {
        "bg": "#1A121E", "card_bg": "#2B1B32", "text": "#FAF5FF", "grid": "#4A2E56",
        "palette": ["#FF6B6B", "#FF8E53", "#FFAA00", "#FF4081", "#9C27B0", "#E040FB"]
    },
    "emerald": {
        "bg": "#0C1E17", "card_bg": "#153328", "text": "#ECFDF5", "grid": "#1F4D3C",
        "palette": ["#10B981", "#34D399", "#059669", "#6EE7B7", "#14B8A6", "#84CC16"]
    },
    "minimal_light": {
        "bg": "#FFFFFF", "card_bg": "#F8FAFC", "text": "#0F172A", "grid": "#E2E8F0",
        "palette": ["#2563EB", "#059669", "#D97706", "#DC2626", "#7C3AED", "#DB2777"]
    }
}


def _parse_list(val):
    """Parse comma or semicolon separated string or return list."""
    if isinstance(val, (list, tuple)):
        return list(val)
    if not val:
        return []
    s = str(val).strip().strip("[]").strip("()")
    items = [x.strip().strip("'").strip('"') for x in s.replace(";", ",").split(",") if x.strip()]
    return items


def _parse_numbers(val):
    """Parse numbers from string or list."""
    items = _parse_list(val)
    numbers = []
    for x in items:
        try:
            numbers.append(float(x))
        except ValueError:
            pass
    return numbers


def run(
    chart_type: str = "bar",
    title: str = "Chart",
    data_y: str = "",
    data_x: str = "",
    x_label: str = "",
    y_label: str = "",
    color_theme: str = "modern_dark",
    output_filename: str = "",
    open_image: bool = True
) -> str:
    """Generate visual graphs from data using Matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # Non-GUI thread-safe backend
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return "Error: matplotlib is not installed. Please run `pip install matplotlib`."

    chart_type_clean = (chart_type or "bar").lower().strip().replace(" ", "_").replace("-", "_")
    theme_key = color_theme.lower().strip() if color_theme else "modern_dark"
    theme = THEME_COLORS.get(theme_key, THEME_COLORS["modern_dark"])
    
    y_values = _parse_numbers(data_y)
    if not y_values:
        return "Error: No valid numerical data provided in `data_y`."
        
    x_labels = _parse_list(data_x)
    if not x_labels or len(x_labels) != len(y_values):
        # Generate default numerical or item labels if mismatched
        if len(x_labels) < len(y_values):
            x_labels = [f"Item {i+1}" for i in range(len(y_values))]
        else:
            x_labels = x_labels[:len(y_values)]
            
    # Destination path
    charts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_charts")
    os.makedirs(charts_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title).strip("_")
    
    if output_filename:
        out_path = os.path.expanduser(output_filename.strip().strip('"').strip("'"))
        if not os.path.isabs(out_path):
            out_path = os.path.join(charts_dir, out_path)
    else:
        out_path = os.path.join(charts_dir, f"{safe_title}_{timestamp}.png")
        
    # Setup Matplotlib styling
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    fig.patch.set_facecolor(theme["bg"])
    ax.set_facecolor(theme["card_bg"])
    
    # Text colors
    ax.tick_params(colors=theme["text"], labelsize=10)
    for spine in ax.spines.values():
        spine.set_color(theme["grid"])
        spine.set_linewidth(1.2)
        
    ax.grid(True, linestyle="--", alpha=0.35, color=theme["grid"])
    palette = theme["palette"]
    colors = [palette[i % len(palette)] for i in range(len(y_values))]

    # 1. Bar Chart
    if chart_type_clean in ("bar", "bar_chart", "column"):
        bars = ax.bar(x_labels, y_values, color=colors, edgecolor=theme["bg"], width=0.6, zorder=3)
        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            val_text = f"{int(height)}" if height.is_integer() else f"{height:.1f}"
            ax.annotate(val_text,
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4), textcoords="offset points",
                        ha='center', va='bottom', color=theme["text"], fontweight='bold', fontsize=9)
                        
    # 2. Horizontal Bar Chart
    elif chart_type_clean in ("horizontal_bar", "hbar"):
        bars = ax.barh(x_labels, y_values, color=colors, edgecolor=theme["bg"], height=0.6, zorder=3)
        for bar in bars:
            width = bar.get_width()
            val_text = f"{int(width)}" if width.is_integer() else f"{width:.1f}"
            ax.annotate(val_text,
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0), textcoords="offset points",
                        ha='left', va='center', color=theme["text"], fontweight='bold', fontsize=9)

    # 3. Line Chart
    elif chart_type_clean in ("line", "line_chart", "trend"):
        line_color = palette[0]
        ax.plot(x_labels, y_values, color=line_color, marker='o', linewidth=3, markersize=8,
                markerfacecolor=palette[1], markeredgecolor=theme["bg"], markeredgewidth=1.5, zorder=4)
        ax.fill_between(range(len(x_labels)), y_values, color=line_color, alpha=0.15)
        for i, (x_val, y_val) in enumerate(zip(x_labels, y_values)):
            val_text = f"{int(y_val)}" if y_val.is_integer() else f"{y_val:.1f}"
            ax.annotate(val_text, xy=(i, y_val), xytext=(0, 7), textcoords="offset points",
                        ha='center', va='bottom', color=theme["text"], fontweight='bold', fontsize=9)

    # 4. Area Chart
    elif chart_type_clean in ("area", "area_chart"):
        line_color = palette[0]
        ax.plot(x_labels, y_values, color=line_color, linewidth=2.5, zorder=4)
        ax.fill_between(range(len(x_labels)), y_values, color=line_color, alpha=0.35, zorder=3)

    # 5. Pie / Doughnut Chart
    elif chart_type_clean in ("pie", "pie_chart", "doughnut", "donut"):
        ax.clear()
        ax.axis('off')
        wedgeprops = dict(width=0.45, edgecolor=theme["bg"], linewidth=2) if "dough" in chart_type_clean or "donut" in chart_type_clean else dict(edgecolor=theme["bg"], linewidth=1.5)
        wedges, texts, autotexts = ax.pie(
            y_values, labels=x_labels, autopct='%1.1f%%',
            startangle=140, colors=colors, wedgeprops=wedgeprops,
            textprops=dict(color=theme["text"], fontsize=10, fontweight='bold'),
            pctdistance=0.75 if "dough" in chart_type_clean or "donut" in chart_type_clean else 0.6
        )
        for autotext in autotexts:
            autotext.set_color("#FFFFFF" if theme_key != "minimal_light" else "#000000")
            autotext.set_fontsize(9)

    # 6. Scatter Plot
    elif chart_type_clean in ("scatter", "scatter_plot", "points"):
        ax.scatter(range(len(x_labels)), y_values, color=palette[0], s=120, edgecolors=palette[1], linewidth=2, zorder=4)
        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels)

    # 7. Histogram
    elif chart_type_clean in ("histogram", "hist", "distribution"):
        n, bins, patches = ax.hist(y_values, bins=max(4, min(10, len(y_values))), color=palette[0], edgecolor=theme["bg"], alpha=0.85, zorder=3)

    # Labels and Titles
    if chart_type_clean not in ("pie", "pie_chart", "doughnut", "donut"):
        if x_label:
            ax.set_xlabel(x_label, color=theme["text"], fontsize=11, fontweight='bold', labelpad=10)
        if y_label:
            ax.set_ylabel(y_label, color=theme["text"], fontsize=11, fontweight='bold', labelpad=10)
        plt.xticks(rotation=25 if len(x_labels) > 5 else 0, ha="right" if len(x_labels) > 5 else "center")

    plt.title(title, color=theme["text"], fontsize=14, fontweight='bold', pad=16)
    plt.tight_layout()
    
    # Save chart image
    plt.savefig(out_path, facecolor=theme["bg"], edgecolor='none', dpi=150)
    plt.close()
    
    # Open image viewer on Windows if requested
    if open_image:
        try:
            if sys.platform == "win32":
                os.startfile(out_path)
            else:
                subprocess.Popen(["xdg-open", out_path])
        except Exception as e:
            logger.warning(f"Could not auto-open image: {e}")
            
    return (
        f"📈 **Chart Generated Successfully!**\n\n"
        f"- **Title:** {title}\n"
        f"- **Chart Type:** {chart_type.replace('_', ' ').title()}\n"
        f"- **Theme:** {theme_key.replace('_', ' ').title()}\n"
        f"- **Data Points:** {len(y_values)}\n"
        f"- **Saved Image:** `{out_path}`\n\n"
        f"🖼️ *Visual graph rendered and opened in your default image viewer.*"
    )
